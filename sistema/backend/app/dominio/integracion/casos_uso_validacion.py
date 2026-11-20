"""Casos de uso del flujo de validacion oficial (Seccion 8.3 del plan
v3, Fase 16) que no tocan el sistema de archivos -- por eso viven aqui y
no en infraestructura/tedef/, igual que MonitorearRespuestaIafas vive en
casos_uso.py mientras GenerarLote/RemitirLote no. Separado de
casos_uso.py para no superar el limite de 400 lineas por archivo
(GUIA_ESTILO_CODIGO.md, Seccion 3).

CargarLoteEnValidador (el orquestador que sube los `.txt`, guarda los
reportes descargados y compone RegistrarResultadoValidador con
RegistrarArchivoTransmision) si necesita filesystem, y por eso vive en
app/infraestructura/tedef/cargar_lote_en_validador.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    DatosRegistrarValidacion,
    ErrorLoteNoCargable,
    IdentidadLoteTedef,
    RepositorioValidacionOficial,
    ResultadoEtapaValidador,
    ValidadorTedefWeb,
)
from app.dominio.integracion.vigencia_lote import exigir_lote_vigente
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    Observabilidad,
    Reloj,
    RepositorioTrabajos,
)

TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR = "CARGAR_LOTE_VALIDADOR"
TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD = "ENVIAR_LOTE_SUSALUD"
# Nueva solicitud de la validacion de un lote ya cargado cuyo trabajo se
# agoto (mismo patron que LOTE_MONITOREO_SOLICITADO).
TIPO_EVENTO_VALIDACION_SOLICITADA = "LOTE_VALIDACION_SOLICITADA"

_ESTADO_GENERADO = "GENERADO"
_ESTADO_CARGADO_VALIDADOR = "CARGADO_VALIDADOR"
_ESTADO_OBSERVADO_VALIDADOR = "OBSERVADO_VALIDADOR"


class SolicitarCargaEnValidador:
    """Seccion 8.3: 'verifica que el lote este GENERADO y encola
    CARGAR_LOTE_VALIDADOR'. Un lote CARGADO_VALIDADOR sin trabajo en curso
    (el anterior agoto sus reintentos) admite una nueva solicitud: el robot
    retoma desde la validacion detallada, sin volver a subirlo."""

    def __init__(
        self,
        repositorio: RepositorioValidacionOficial,
        repositorio_trabajos: RepositorioTrabajos,
        reloj: Reloj,
        observabilidad: Observabilidad | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._reloj = reloj
        self._observabilidad = observabilidad

    async def ejecutar(self, lote_id: int, actor: str) -> int:
        estado = await self._repositorio.obtener_estado_lote(lote_id)
        if estado is None:
            raise ErrorLoteNoCargable(f"No existe el lote {lote_id}.")
        if estado == _ESTADO_CARGADO_VALIDADOR:
            await self._exigir_sin_trabajo_en_curso(lote_id)
        elif estado != _ESTADO_GENERADO:
            raise ErrorLoteNoCargable(
                f"El lote {lote_id} esta en estado {estado!r}; solo se puede cargar "
                f"en el validador un lote en estado {_ESTADO_GENERADO!r}."
            )
        exigir_lote_vigente(await self._repositorio.vigencia_lote(lote_id))
        trabajo_id = await self._repositorio_trabajos.encolar(
            tipo=TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
            # Control C-07 (Seccion 5.2.7): el robot carga el lote mas
            # tarde, en otro proceso -- "usuario_origen" es como sus
            # eventos saben a que analista atribuirselo.
            carga_util={"lote_id": lote_id, "usuario_origen": actor},
            proximo_intento=self._reloj.ahora(),
        )
        if estado == _ESTADO_CARGADO_VALIDADOR and self._observabilidad is not None:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=None,
                    lote_id=lote_id,
                    tipo_evento=TIPO_EVENTO_VALIDACION_SOLICITADA,
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"lote_id": lote_id, "trabajo_id": trabajo_id},
                )
            )
        return trabajo_id

    async def _exigir_sin_trabajo_en_curso(self, lote_id: int) -> None:
        if await self._repositorio_trabajos.hay_sin_terminar(
            TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR, lote_id
        ):
            raise ErrorLoteNoCargable(f"El lote {lote_id} ya tiene una validacion en curso.")


@dataclass(frozen=True, slots=True)
class DatosValidacionEtapa:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    RegistrarResultadoValidador necesita para persistir el resultado de
    una etapa (FORMA o DETALLADA)."""

    lote_id: int
    trabajo_id: int | None
    etapa: str  # 'FORMA' | 'DETALLADA'
    estado_previo: str
    resultado: ResultadoEtapaValidador
    ruta_reporte: str | None
    sha256_reporte: str | None
    inicio: datetime
    fin: datetime
    usuario_origen: str | None = None


class RegistrarResultadoValidador:
    """Seccion 8.3: 'persiste validacion_oficial y observacion_validador
    a partir de lo que devuelve el robot; cambia el estado del lote'."""

    def __init__(
        self, repositorio: RepositorioValidacionOficial, observabilidad: Observabilidad
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad

    async def ejecutar(self, datos: DatosValidacionEtapa, actor: str) -> int:
        validacion_id = await self._repositorio.registrar_validacion(
            DatosRegistrarValidacion(
                lote_id=datos.lote_id,
                trabajo_id=datos.trabajo_id,
                etapa=datos.etapa,
                resultado=datos.resultado,
                ruta_reporte=datos.ruta_reporte,
                sha256_reporte=datos.sha256_reporte,
                instante=datos.fin,
            )
        )
        await self._registrar_medicion(datos, actor)
        await self._registrar_evento_si_corresponde(datos, actor)
        return validacion_id

    async def _registrar_medicion(self, datos: DatosValidacionEtapa, actor: str) -> None:
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="validacion_oficial",
                inicio=datos.inicio,
                fin=datos.fin,
                actor=actor,
                lote_id=datos.lote_id,
                resultado="conforme" if datos.resultado.conforme else "observado",
                datos={
                    "etapa": datos.etapa,
                    "observaciones": len(datos.resultado.observaciones),
                    "usuario_origen": datos.usuario_origen,
                },
            )
        )

    async def _registrar_evento_si_corresponde(
        self, datos: DatosValidacionEtapa, actor: str
    ) -> None:
        # Seccion 10: solo hay evento para LOTE_CARGADO_VALIDADOR (forma
        # conforme) y LOTE_OBSERVADO_VALIDADOR (observado en cualquier
        # etapa). La validacion detallada conforme no tiene evento
        # propio -- RegistrarArchivoTransmision emite LOTE_VALIDADO por
        # separado cuando el `.S01` ya esta en mano.
        if not datos.resultado.conforme:
            tipo_evento, estado_nuevo = "LOTE_OBSERVADO_VALIDADOR", _ESTADO_OBSERVADO_VALIDADOR
        elif datos.etapa == "FORMA":
            tipo_evento, estado_nuevo = "LOTE_CARGADO_VALIDADOR", _ESTADO_CARGADO_VALIDADOR
        else:
            return
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=datos.lote_id,
                tipo_evento=tipo_evento,
                actor=actor,
                estado_previo=datos.estado_previo,
                estado_nuevo=estado_nuevo,
                datos={"lote_id": datos.lote_id, "etapa": datos.etapa},
                usuario_origen=datos.usuario_origen,
            )
        )


@dataclass(frozen=True, slots=True)
class DatosArchivoTransmision:
    """Objeto de parametros: lo que RegistrarArchivoTransmision necesita
    para dejar constancia del `.S01` ya descargado y ya escrito en el
    volumen de artefactos."""

    lote_id: int
    archivo_s01: ArchivoLote
    ruta_s01: str
    sha256_s01: str
    inicio: datetime
    fin: datetime
    usuario_origen: str | None = None


class RegistrarArchivoTransmision:
    """Seccion 8.3: 'guarda el .S01 en el almacen de artefactos, calcula
    SHA-256, registra nombre y huella, estado VALIDADO'. El calculo de
    la huella y la escritura del archivo ya ocurrieron en
    CargarLoteEnValidador (infraestructura); este caso de uso solo
    persiste lo que ya se obtuvo."""

    def __init__(
        self, repositorio: RepositorioValidacionOficial, observabilidad: Observabilidad
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad

    async def ejecutar(self, datos: DatosArchivoTransmision, actor: str) -> None:
        await self._repositorio.registrar_archivo_transmision(
            lote_id=datos.lote_id,
            archivo=datos.archivo_s01,
            ruta_s01=datos.ruta_s01,
            sha256_s01=datos.sha256_s01,
            instante=datos.fin,
        )
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="obtencion_s01",
                inicio=datos.inicio,
                fin=datos.fin,
                actor=actor,
                lote_id=datos.lote_id,
                resultado="validado",
                datos={
                    "nombre_s01": datos.archivo_s01.nombre,
                    "sha256_s01": datos.sha256_s01,
                    "usuario_origen": datos.usuario_origen,
                },
            )
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=datos.lote_id,
                tipo_evento="LOTE_VALIDADO",
                actor=actor,
                estado_previo=_ESTADO_CARGADO_VALIDADOR,
                estado_nuevo="VALIDADO",
                datos={"lote_id": datos.lote_id, "nombre_s01": datos.archivo_s01.nombre},
                usuario_origen=datos.usuario_origen,
            )
        )


class SolicitarEnvioSusalud:
    """Seccion 8.3: encola ENVIAR_LOTE_SUSALUD para los lotes del periodo
    ya remitidos a la IAFAS (REMITIDO_IAFAS o ACEPTADO), que son los que la
    norma pide reportar. Un solo trabajo por periodo, con todos
    los lotes pendientes de envio -- el propio validador TEDEF Web
    selecciona varios lotes a la vez en 'Enviar Lotes' (Seccion 9.2)."""

    def __init__(
        self,
        repositorio: RepositorioValidacionOficial,
        repositorio_trabajos: RepositorioTrabajos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._reloj = reloj

    async def ejecutar(self, periodo: str, actor: str) -> int | None:
        lotes = await self._repositorio.obtener_lotes_para_envio_susalud(periodo)
        if not lotes:
            return None
        return await self._repositorio_trabajos.encolar(
            tipo=TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD,
            carga_util={
                "periodo": periodo,
                "lotes": [
                    {"lote_id": lote.lote_id, "numero": lote.numero, "periodo": lote.periodo}
                    for lote in lotes
                ],
                # Control C-07 (Seccion 5.2.7): atribuye LOTE_ENVIADO_SUSALUD,
                # que ejecuta el robot, al analista que pidio el envio.
                "usuario_origen": actor,
            },
            proximo_intento=self._reloj.ahora(),
        )


@dataclass(frozen=True, slots=True)
class LoteEnvioSusalud:
    """Lo que llega en la carga util del trabajo ENVIAR_LOTE_SUSALUD
    (Seccion 8.3): un lote a marcar enviado, con lo minimo para que el
    robot vuelva a encontrar su fila en el validador."""

    lote_id: int
    numero: str
    periodo: str


class EnviarLoteSusalud:
    """Ejecuta el trabajo ENVIAR_LOTE_SUSALUD (Seccion 8.3, 8.7): no
    toca filesystem (el `.S01` ya esta en el validador, no en este
    sistema), por eso vive aqui y no en infraestructura/tedef/, a
    diferencia de CargarLoteEnValidador."""

    def __init__(
        self,
        repositorio: RepositorioValidacionOficial,
        validador: ValidadorTedefWeb,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._validador = validador
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(
        self,
        lotes: tuple[LoteEnvioSusalud, ...],
        periodo: str,
        actor: str,
        usuario_origen: str | None = None,
    ) -> None:
        inicio = self._reloj.ahora()
        identidades = tuple(
            IdentidadLoteTedef(numero=lote.numero, periodo=lote.periodo) for lote in lotes
        )
        await self._validador.enviar_a_susalud(identidades)
        fin = self._reloj.ahora()

        lote_ids = tuple(lote.lote_id for lote in lotes)
        await self._repositorio.marcar_enviados_susalud(lote_ids, fin)
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="envio_susalud",
                inicio=inicio,
                fin=fin,
                actor=actor,
                resultado="enviado",
                datos={
                    "periodo": periodo,
                    "lotes": len(lote_ids),
                    "usuario_origen": usuario_origen,
                },
            )
        )
        for lote_id in lote_ids:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=None,
                    lote_id=lote_id,
                    tipo_evento="LOTE_ENVIADO_SUSALUD",
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"lote_id": lote_id, "periodo": periodo},
                    usuario_origen=usuario_origen,
                )
            )
