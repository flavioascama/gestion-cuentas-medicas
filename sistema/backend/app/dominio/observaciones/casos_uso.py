"""Casos de uso del contexto de observaciones/glosas: CU-08 (registrar y
clasificar), CU-09 (asignar/reasignar el responsable) y CU-10, su mitad
de "elaborar la respuesta" (la refacturacion de CU-10 es del modulo de
codificacion CPMS, Seccion 5.2.4.2 y 8.2 -- este caso de uso solo cierra
el lado de la observacion y de la cuenta)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.puertos import RepositorioUsuarios
from app.dominio.observaciones.entrega import ConsultaEntregas, con_entrega
from app.dominio.observaciones.errores import (
    ErrorMontoObservadoExcedeFacturado,
    ErrorMontoObservadoNoValido,
    ErrorMotivoInexistente,
    ErrorObservacionDeOtroResponsable,
    ErrorObservacionInexistente,
    ErrorObservacionYaRespondida,
    ErrorResponsableNoValido,
    ErrorRespuestaConComprobanteDesfasado,
)
from app.dominio.observaciones.puertos import RepositorioCatalogoMotivos, RepositorioObservaciones
from app.dominio.observaciones.valores import (
    ROL_RESPONSABLE_POR_NATURALEZA,
    DatosNuevaObservacion,
    DatosRegistroObservacion,
    MotivoObservacion,
    Naturaleza,
    Observacion,
    Respondedor,
    ResultadoObservacion,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.pse.puertos import RepositorioCotejoComprobante
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

# Una cuenta ya glosada (total o parcial) puede recibir otra observacion
# de la aseguradora: se registra igual, sin transicion, porque la Tabla 58
# no define una y el estado ya es el que corresponde.
_ESTADOS_GLOSADOS = frozenset({"GLOSADA", "GLOSADA_PARCIAL"})
TIPO_EVENTO_OBSERVACION_ADICIONAL = "OBSERVACION_ADICIONAL"
_ETIQUETA_ROL = {NombreRol.ANALISTA: "Analista", NombreRol.AUDITOR: "Auditor"}


async def _exigir_dentro_de_lo_facturado(
    repositorio: RepositorioObservaciones, datos: DatosRegistroObservacion
) -> None:
    # La glosa total puede ir sin monto; la parcial lo exige (tercera
    # auditoria, medio 1). Sin el monto del comprobante no hay que comparar.
    monto = datos.monto_observado
    if monto is None:
        if datos.es_parcial:
            raise ErrorMontoObservadoNoValido("Una glosa parcial debe indicar el monto observado.")
        return
    if monto <= 0:
        raise ErrorMontoObservadoNoValido("El monto observado debe ser mayor que S/ 0.00.")
    facturado = await repositorio.total_facturado(datos.cuenta_medica_id)
    if facturado is not None and monto > facturado:
        raise ErrorMontoObservadoExcedeFacturado(monto, facturado)
    if facturado is not None and datos.es_parcial and monto == facturado:
        raise ErrorMontoObservadoNoValido(
            f"Una glosa parcial debe ser menor que el total facturado de la cuenta "
            f"(S/ {facturado:,.2f}): por S/ {monto:,.2f} regístrela como glosa total."
        )


def _exigir_responsable(observacion: Observacion, respondedor: Respondedor | None) -> None:
    """Con responsable asignado, solo esa persona responde; sin el, quien
    tenga el rol responsable (la misma regla de la pantalla)."""
    asignado = observacion.responsable_usuario_id
    if asignado is not None:
        if respondedor is None or respondedor.usuario_id != asignado:
            raise ErrorObservacionDeOtroResponsable(
                "La observación está asignada a otra persona: la responde ella."
            )
        return
    if respondedor is not None and observacion.responsable_rol not in respondedor.roles:
        etiqueta = _ETIQUETA_ROL.get(observacion.responsable_rol, observacion.responsable_rol)
        raise ErrorObservacionDeOtroResponsable(
            f"La observación la responde una persona con el rol {etiqueta}."
        )


@dataclass(frozen=True, slots=True)
class _PasoRegistro:
    tipo_evento: str
    estado_previo: str | None
    estado_nuevo: str | None
    estado_final: str


def _paso_de_registro(estado_actual: str | None, es_parcial: bool) -> _PasoRegistro:
    if estado_actual is not None and estado_actual in _ESTADOS_GLOSADOS:
        return _PasoRegistro(TIPO_EVENTO_OBSERVACION_ADICIONAL, None, None, estado_actual)
    transicion = _transicion_de_registro(estado_actual, es_parcial)
    estado_nuevo = validar_transicion(estado_actual, transicion)
    return _PasoRegistro(transicion.value, estado_actual, estado_nuevo, estado_nuevo)


def _transicion_de_registro(estado_actual: str | None, es_parcial: bool) -> TipoTransicion:
    """CU-08: la precondicion admite dos estados de origen distintos
    (Seccion 5.2.3.3) -- EN_AUDITORIA (primera observacion, T-07) o
    SUBSANADA (la aseguradora insiste tras una respuesta, T-09, que la
    Tabla 58 solo define para el caso total). Fuera de ambos, se
    devuelve GLOSA igual: el motor es quien debe rechazarla, con el
    mismo error que cualquier otra transicion no definida."""

    if estado_actual == "SUBSANADA":
        return TipoTransicion.NUEVA_OBSERVACION
    return TipoTransicion.GLOSA_PARCIAL if es_parcial else TipoTransicion.GLOSA


@dataclass(frozen=True, slots=True)
class ResultadoRegistroObservacion:
    observacion_id: int
    naturaleza: Naturaleza
    responsable_rol: NombreRol
    estado_cuenta: str


class RegistrarObservacion:
    """CU-08 (RF-09, RF-10, RF-16): clasifica por el motivo, asigna el
    responsable por naturaleza y lleva la cuenta a GLOSADA, GLOSADA_
    PARCIAL (T-07) o de vuelta a GLOSADA desde SUBSANADA (T-09). Si la
    cuenta ya esta GLOSADA o GLOSADA_PARCIAL, la registra sin mover el
    estado."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        catalogo: RepositorioCatalogoMotivos,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._catalogo = catalogo
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, datos: DatosRegistroObservacion) -> ResultadoRegistroObservacion:
        motivo = await self._catalogo.obtener(datos.motivo_codigo)
        if motivo is None:
            raise ErrorMotivoInexistente(
                f"El motivo {datos.motivo_codigo!r} no existe en el catálogo vigente."
            )
        await _exigir_dentro_de_lo_facturado(self._repositorio, datos)
        estado_actual = await self._estado_cuenta.obtener_estado(datos.cuenta_medica_id)
        paso = _paso_de_registro(estado_actual, datos.es_parcial)

        responsable_rol = ROL_RESPONSABLE_POR_NATURALEZA[motivo.naturaleza]
        ahora = self._reloj.ahora()
        await self._mantener_si_subsanada(datos.cuenta_medica_id, estado_actual, ahora)
        observacion_id = await self._repositorio.crear(
            DatosNuevaObservacion(
                cuenta_medica_id=datos.cuenta_medica_id,
                motivo_codigo=motivo.codigo,
                naturaleza=motivo.naturaleza,
                es_parcial=datos.es_parcial,
                detalle_campo_objetado=datos.detalle_campo_objetado,
                responsable_rol=responsable_rol,
                registrado_en=ahora,
                monto_observado=datos.monto_observado,
            )
        )
        if paso.estado_nuevo is not None:
            await self._estado_cuenta.fijar_estado(datos.cuenta_medica_id, paso.estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=datos.cuenta_medica_id,
                tipo_evento=paso.tipo_evento,
                actor=datos.actor,
                estado_previo=paso.estado_previo,
                estado_nuevo=paso.estado_nuevo,
                datos={
                    "observacion_id": observacion_id,
                    "motivo_codigo": motivo.codigo,
                    "naturaleza": motivo.naturaleza.value,
                    "es_parcial": datos.es_parcial,
                    "responsable_rol": responsable_rol.value,
                },
                usuario_origen=datos.usuario_origen,
            )
        )
        return ResultadoRegistroObservacion(
            observacion_id=observacion_id,
            naturaleza=motivo.naturaleza,
            responsable_rol=responsable_rol,
            estado_cuenta=paso.estado_final,
        )

    async def _mantener_si_subsanada(
        self, cuenta_medica_id: int, estado_actual: str | None, ahora: datetime
    ) -> None:
        # T-09: la aseguradora mantiene su objecion sobre lo respondido.
        if estado_actual == "SUBSANADA":
            await self._repositorio.fijar_resultado(
                cuenta_medica_id, ResultadoObservacion.MANTENIDA, ahora
            )


class AsignarResponsableObservacion:
    """CU-09 (RF-10, RF-16): el jefe confirma o reasigna. Si corrige la
    naturaleza, el responsable propuesto se recalcula (Seccion 5.2.4.2);
    no mueve el estado de la cuenta, por eso no pasa por el motor.

    Con `usuarios` (2026-11-18) comprueba que la persona elegida exista,
    este activa y tenga el rol que responde esa naturaleza: antes se
    aceptaba cualquier numero de usuario."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        observabilidad: Observabilidad,
        usuarios: RepositorioUsuarios | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad
        self._usuarios = usuarios

    async def ejecutar(
        self,
        observacion_id: int,
        actor: str,
        responsable_usuario_id: int | None,
        naturaleza_corregida: Naturaleza | None = None,
    ) -> None:
        observacion = await self._repositorio.obtener(observacion_id)
        if observacion is None:
            raise ErrorObservacionInexistente("No existe la observación.")

        naturaleza_final = naturaleza_corregida or observacion.naturaleza
        responsable_rol = ROL_RESPONSABLE_POR_NATURALEZA[naturaleza_final]
        await self._exigir_responsable_valido(responsable_usuario_id, responsable_rol)
        await self._repositorio.reasignar(
            observacion_id, naturaleza_final, responsable_rol, responsable_usuario_id
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=observacion.cuenta_medica_id,
                tipo_evento="OBSERVACION_REASIGNADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "observacion_id": observacion_id,
                    "naturaleza_anterior": observacion.naturaleza.value,
                    "naturaleza_nueva": naturaleza_final.value,
                    "responsable_rol": responsable_rol.value,
                    "responsable_usuario_id": responsable_usuario_id,
                },
            )
        )

    async def _exigir_responsable_valido(self, usuario_id: int | None, rol: NombreRol) -> None:
        if usuario_id is None or self._usuarios is None:
            return
        usuario = await self._usuarios.obtener_por_id(usuario_id)
        if usuario is None or not usuario.activo or rol not in usuario.roles:
            raise ErrorResponsableNoValido(
                f"El responsable debe ser un usuario activo con el rol {rol.value}."
            )


class ListarResponsablesPosibles:
    """CU-09: las personas a las que el jefe puede asignar una observacion
    (2026-11-18: antes escribia el numero interno del usuario). Son los
    usuarios activos con un rol que responde observaciones (Tabla 60)."""

    def __init__(self, usuarios: RepositorioUsuarios) -> None:
        self._usuarios = usuarios

    async def ejecutar(self) -> list[Usuario]:
        roles = frozenset(ROL_RESPONSABLE_POR_NATURALEZA.values())
        usuarios = await self._usuarios.listar()
        return [u for u in usuarios if u.activo and u.tiene_alguno(roles)]


class ResponderObservacion:
    """CU-10, lado de la observacion y la cuenta (RF-08, RF-11, RF-16):
    responder cierra el control de plazo de la observacion y, si la cuenta
    esta GLOSADA y ya no le queda otra observacion ABIERTA, la lleva a
    SUBSANADA (T-08), sea la respondida total o parcial: una parcial que
    llego sobre SUBSANADA la devolvio a GLOSADA y sin esto quedaria ahi.
    GLOSADA_PARCIAL no se mueve -- Tabla 58/65/66 solo definen GLOSADA_
    PARCIAL -> LIQUIDADA_PARCIAL (T-10, CU-12, a cargo de tesoreria).

    Con `cotejo` (2026-11-21), la respuesta no sale mientras el comprobante
    vigente no refleje la cuenta: en GLOSADA y GLOSADA_PARCIAL se pueden
    cambiar procedimientos y productos, y antes hay que emitir el
    comprobante de reemplazo."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
        cotejo: RepositorioCotejoComprobante | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._cotejo = cotejo

    async def ejecutar(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: str | None,
        actor: str,
        respondedor: Respondedor | None = None,
    ) -> None:
        observacion = await self._repositorio.obtener(observacion_id)
        if observacion is None:
            raise ErrorObservacionInexistente("No existe la observación.")
        if observacion.estado == "RESPONDIDA":
            raise ErrorObservacionYaRespondida("La observación ya tiene una respuesta registrada.")
        _exigir_responsable(observacion, respondedor)
        await self._exigir_comprobante_al_dia(observacion.cuenta_medica_id)
        usuario_origen = respondedor.nombre_usuario if respondedor is not None else None

        ahora = self._reloj.ahora()
        estado_previo: str | None = None
        estado_nuevo: str | None = None
        estado_actual = await self._estado_cuenta.obtener_estado(observacion.cuenta_medica_id)
        if estado_actual == "GLOSADA" and not await self._quedan_otras_abiertas(observacion):
            estado_nuevo = validar_transicion(estado_actual, TipoTransicion.SUBSANACION)
            await self._estado_cuenta.fijar_estado(observacion.cuenta_medica_id, estado_nuevo)
            estado_previo = estado_actual

        await self._repositorio.responder(
            observacion_id, respuesta_texto, respuesta_sustento, ahora
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=observacion.cuenta_medica_id,
                tipo_evento="OBSERVACION_RESPONDIDA",
                actor=actor,
                estado_previo=estado_previo,
                estado_nuevo=estado_nuevo,
                datos={
                    "observacion_id": observacion_id,
                    "es_parcial": observacion.es_parcial,
                },
                usuario_origen=usuario_origen,
            )
        )

    async def _exigir_comprobante_al_dia(self, cuenta_medica_id: int) -> None:
        if self._cotejo is not None and (await self._cotejo.cotejar(cuenta_medica_id)).desfasado:
            raise ErrorRespuestaConComprobanteDesfasado()

    async def _quedan_otras_abiertas(self, observacion: Observacion) -> bool:
        # La cuenta sigue glosada mientras otra observacion espere respuesta.
        otras = await self._repositorio.listar_por_cuenta(observacion.cuenta_medica_id)
        return any(o.id != observacion.id and o.estado == "ABIERTA" for o in otras)


class ListarObservacionesPorCuenta:
    """Consulta de solo lectura (Seccion 5.2: "ninguna regla de negocio
    en una ruta" -- hasta una consulta directa pasa por un caso de uso,
    nunca un repositorio llamado desde la ruta)."""

    def __init__(
        self, repositorio: RepositorioObservaciones, entregas: ConsultaEntregas | None = None
    ) -> None:
        self._repositorio = repositorio
        self._entregas = entregas

    async def ejecutar(self, cuenta_medica_id: int) -> list[Observacion]:
        observaciones = await self._repositorio.listar_por_cuenta(cuenta_medica_id)
        if self._entregas is None:
            return observaciones
        hechos = await self._entregas.hechos(cuenta_medica_id)
        return [con_entrega(o, hechos.get(o.id)) for o in observaciones]


class ListarCatalogoMotivos:
    """CU-08, flujo alternativo: la pantalla necesita listar las
    opciones del catalogo para que el analista elija el codigo."""

    def __init__(self, catalogo: RepositorioCatalogoMotivos) -> None:
        self._catalogo = catalogo

    async def ejecutar(self) -> list[MotivoObservacion]:
        return await self._catalogo.listar()
