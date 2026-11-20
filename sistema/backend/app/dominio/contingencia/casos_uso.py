"""Casos de uso del modo de contingencia (RF-23, AD-13, C-18): habilitarlo
solo ante una plataforma no disponible, registrar la cobertura a mano
(CU-01), listar los registros y revisarlos (jefe de cuentas medicas).

El registro manual de la validacion del lote (CU-03) escribe el `.S01` en
disco y por eso vive en infraestructura/tedef/, igual que RemitirLote."""

from __future__ import annotations

from decimal import Decimal

from app.dominio.acreditacion.casos_uso import TIPO_TRABAJO_CONSULTAR_COBERTURA
from app.dominio.acreditacion.puertos import ErrorCuentaNoEncontrada, RepositorioAcreditacion
from app.dominio.acreditacion.valores import (
    ResultadoAcreditacion,
    admite_consulta,
    mensaje_asegurado_no_encontrado,
)
from app.dominio.contingencia.errores import (
    ErrorContingenciaNoHabilitada,
    ErrorCopagoIncompleto,
    ErrorRegistroContingenciaInexistente,
    ErrorRegistroContingenciaYaRevisado,
    ErrorSustentoInsuficiente,
)
from app.dominio.contingencia.puertos import RepositorioContingencia
from app.dominio.contingencia.valores import (
    COMPONENTE_REGISTRO_MANUAL,
    LONGITUD_MINIMA_SUSTENTO,
    TIPO_EVENTO_COBERTURA_CONTINGENCIA,
    TIPO_EVENTO_REVISION_CONTINGENCIA,
    EstadoRevision,
    RegistroContingencia,
    ResultadoConsulta,
    UltimaConsultaCobertura,
    clasificar_consulta,
)
from app.dominio.integracion.casos_uso_validacion import TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

# Estados desde los que un lote espera el resultado del validador.
ESTADOS_LOTE_ESPERANDO_VALIDADOR = frozenset({"GENERADO", "CARGADO_VALIDADOR"})


def validar_sustento(sustento: str) -> str:
    limpio = sustento.strip()
    if len(limpio) < LONGITUD_MINIMA_SUSTENTO:
        raise ErrorSustentoInsuficiente(
            "El registro en contingencia exige su sustento (control C-18): describa la "
            f"constancia obtenida en al menos {LONGITUD_MINIMA_SUSTENTO} caracteres."
        )
    return limpio


def normalizar_copago(
    tipo: str | None, monto: Decimal | None, porcentaje: int | None
) -> tuple[str | None, Decimal | None, int | None]:
    """El copago registrado a mano, con los mismos valores que deja el
    robot ('fijo' con su monto, 'coaseguro' con su porcentaje, o ninguno)
    para que el calculo de montos lo use igual."""
    if tipo == "fijo":
        if monto is None or monto <= 0:
            raise ErrorCopagoIncompleto("El copago de monto fijo exige su monto.")
        return "fijo", monto, None
    if tipo == "coaseguro":
        if porcentaje is None or not 0 < porcentaje <= 100:
            raise ErrorCopagoIncompleto("El coaseguro exige su porcentaje (de 1 a 100).")
        return "coaseguro", None, porcentaje
    return None, None, None


class ConsultarDisponibilidadContingencia:
    def __init__(
        self, repositorio: RepositorioContingencia, acreditaciones: RepositorioAcreditacion
    ) -> None:
        self._repositorio = repositorio
        self._acreditaciones = acreditaciones

    async def cobertura(self, cuenta_medica_id: int) -> bool:
        if await self._acreditaciones.existe_acreditacion(
            cuenta_medica_id
        ) and not await self._acreditacion_reemplazable(cuenta_medica_id):
            return False
        ultimo = await self._repositorio.ultimo_trabajo(
            TIPO_TRABAJO_CONSULTAR_COBERTURA, "cuenta_medica_id", cuenta_medica_id
        )
        # Solo una plataforma que no respondio habilita la contingencia; un
        # asegurado no encontrado es una respuesta, no una indisponibilidad.
        return ultimo is not None and clasificar_consulta(ultimo) is ResultadoConsulta.SIN_RESPUESTA

    async def _acreditacion_reemplazable(self, cuenta_medica_id: int) -> bool:
        # La acreditacion revisada no conforme admite un nuevo registro
        # mientras la cuenta siga sin comprobante.
        if not await self._repositorio.cobertura_vigente_no_conforme(cuenta_medica_id):
            return False
        contexto = await self._acreditaciones.obtener_contexto_cuenta(cuenta_medica_id)
        return contexto is not None and admite_consulta(contexto, ya_acreditada=True)

    async def validacion(self, lote_id: int) -> bool:
        estado = await self._repositorio.obtener_estado_lote(lote_id)
        if estado not in ESTADOS_LOTE_ESPERANDO_VALIDADOR:
            return False
        ultimo = await self._repositorio.ultimo_trabajo(
            TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR, "lote_id", lote_id
        )
        return ultimo is not None and ultimo.estado == "AGOTADO"


class ConsultarUltimaConsultaCobertura:
    """Como termino la ultima consulta de ACREDITA SALUD de la cuenta, para
    que la seccion de acreditacion la muestre aunque se recargue la pagina
    (antes solo se veia el progreso del trabajo recien pedido, con el texto
    interno del robot)."""

    def __init__(
        self, repositorio: RepositorioContingencia, acreditaciones: RepositorioAcreditacion
    ) -> None:
        self._repositorio = repositorio
        self._acreditaciones = acreditaciones

    async def ejecutar(self, cuenta_medica_id: int) -> UltimaConsultaCobertura | None:
        ultimo = await self._repositorio.ultimo_trabajo(
            TIPO_TRABAJO_CONSULTAR_COBERTURA, "cuenta_medica_id", cuenta_medica_id
        )
        if ultimo is None:
            return None
        resultado = clasificar_consulta(ultimo)
        mensaje = None
        if resultado is ResultadoConsulta.SIN_RESULTADO:
            contexto = await self._acreditaciones.obtener_contexto_cuenta(cuenta_medica_id)
            if contexto is not None:
                mensaje = mensaje_asegurado_no_encontrado(
                    contexto.tipo_documento_paciente, contexto.numero_documento_paciente
                )
        return UltimaConsultaCobertura(
            resultado=resultado,
            intentos=ultimo.intentos,
            solicitada_en=ultimo.creado_en,
            actualizada_en=ultimo.actualizado_en,
            mensaje=mensaje,
        )


class RegistrarCoberturaContingencia:
    """CU-01, flujo alternativo: ACREDITA SALUD no respondio tras los
    reintentos; el analista registra el resultado que obtuvo por otro medio
    (por ejemplo, la constancia de la IAFAS) con su codigo de acreditacion.
    La acreditacion queda como cualquier otra (cuenta la pieza de
    completitud) pero con componente ejecutor "registro manual"."""

    def __init__(
        self,
        disponibilidad: ConsultarDisponibilidadContingencia,
        acreditaciones: RepositorioAcreditacion,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._disponibilidad = disponibilidad
        self._acreditaciones = acreditaciones
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(
        self, cuenta_medica_id: int, resultado: ResultadoAcreditacion, sustento: str, actor: str
    ) -> int:
        sustento_limpio = validar_sustento(sustento)
        if await self._acreditaciones.obtener_contexto_cuenta(cuenta_medica_id) is None:
            raise ErrorCuentaNoEncontrada(f"No existe la cuenta medica {cuenta_medica_id}.")
        if not await self._disponibilidad.cobertura(cuenta_medica_id):
            raise ErrorContingenciaNoHabilitada(
                "El modo de contingencia de cobertura solo se habilita cuando la ultima "
                "verificacion de esta cuenta agoto sus reintentos y no hay acreditacion."
            )
        acreditacion_id = await self._acreditaciones.guardar_acreditacion(
            cuenta_medica_id=cuenta_medica_id,
            resultado=resultado,
            instante=self._reloj.ahora(),
            duracion_ms=0,
            componente_ejecutor=COMPONENTE_REGISTRO_MANUAL,
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_COBERTURA_CONTINGENCIA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "modo": "contingencia",
                    "acreditacion_id": acreditacion_id,
                    "condicion_cobertura": resultado.condicion_cobertura,
                    "codigo_autorizacion": resultado.codigo_autorizacion,
                    "sustento": sustento_limpio,
                },
            )
        )
        return acreditacion_id


class ListarRegistrosContingencia:
    def __init__(self, repositorio: RepositorioContingencia) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, solo_pendientes: bool = False) -> list[RegistroContingencia]:
        registros = await self._repositorio.listar_registros()
        if solo_pendientes:
            return [r for r in registros if r.estado_revision is EstadoRevision.PENDIENTE]
        return registros


class RevisarRegistroContingencia:
    """C-18: "se somete a la revision posterior del jefe de cuentas
    medicas". La revision es un evento mas del mismo agregado (la cuenta o
    el lote), no una modificacion del registro original, que es inmutable."""

    def __init__(
        self, repositorio: RepositorioContingencia, observabilidad: Observabilidad
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad

    async def ejecutar(self, evento_id: str, conforme: bool, comentario: str, actor: str) -> None:
        registro = next(
            (r for r in await self._repositorio.listar_registros() if r.evento_id == evento_id),
            None,
        )
        if registro is None:
            raise ErrorRegistroContingenciaInexistente(
                f"No existe el registro en contingencia {evento_id}."
            )
        if registro.estado_revision is not EstadoRevision.PENDIENTE:
            raise ErrorRegistroContingenciaYaRevisado(
                f"El registro en contingencia {evento_id} ya fue revisado."
            )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=registro.cuenta_medica_id,
                lote_id=registro.lote_id if registro.cuenta_medica_id is None else None,
                tipo_evento=TIPO_EVENTO_REVISION_CONTINGENCIA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "registro_evento_id": evento_id,
                    "conforme": conforme,
                    "comentario": comentario.strip(),
                },
            )
        )
