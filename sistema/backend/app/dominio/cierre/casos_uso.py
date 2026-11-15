"""Casos de uso del contexto de cierre y anulacion de la cuenta medica:
CU-13, "cerrar o anular la cuenta medica" (Tabla 52). El cierre (T-12)
es responsabilidad del analista; la anulacion (T-13, RF-21) la solicita
el analista y la aprueba o rechaza el jefe de cuentas medicas -- dos
casos de uso separados por eso, `SolicitarAnulacion` y
`ResolverSolicitudAnulacion`, igual que CU-08/CU-09 se separaron en
`RegistrarObservacion`/`AsignarResponsableObservacion` (Fase 26)."""

from __future__ import annotations

from app.dominio.cierre.errores import (
    ErrorDiferenciaPendiente,
    ErrorObservacionPendiente,
    ErrorSinLiquidacion,
    ErrorSolicitudAnulacionInexistente,
    ErrorSolicitudAnulacionYaPendiente,
    ErrorSolicitudAnulacionYaResuelta,
)
from app.dominio.cierre.puertos import RepositorioSolicitudesAnulacion
from app.dominio.cierre.valores import (
    DatosNuevaSolicitudAnulacion,
    EstadoSolicitudAnulacion,
    SolicitudAnulacion,
)
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.observaciones.puertos import RepositorioObservaciones
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES, TipoTransicion
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj


class CerrarCuenta:
    """CU-13, T-12 (RF-08, RF-16, RF-21): precondicion "PAGADA o PAGADA_
    PARCIAL sin observaciones pendientes" y "el sistema verifica que el
    monto conciliado corresponda al liquidado" (Tabla 52)."""

    def __init__(
        self,
        liquidaciones: RepositorioLiquidaciones,
        observaciones: RepositorioObservaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
    ) -> None:
        self._liquidaciones = liquidaciones
        self._observaciones = observaciones
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad

    async def ejecutar(self, cuenta_medica_id: int, actor: str) -> str:
        liquidacion = await self._liquidaciones.obtener_por_cuenta(cuenta_medica_id)
        if liquidacion is None or liquidacion.diferencia is None:
            raise ErrorSinLiquidacion(
                f"La cuenta {cuenta_medica_id} no tiene un pago conciliado todavia."
            )
        if liquidacion.diferencia != 0:
            raise ErrorDiferenciaPendiente(
                f"La cuenta {cuenta_medica_id} tiene una diferencia de conciliacion "
                f"({liquidacion.diferencia}) sin resolver."
            )
        observaciones_abiertas = [
            o
            for o in await self._observaciones.listar_por_cuenta(cuenta_medica_id)
            if o.estado == "ABIERTA"
        ]
        if observaciones_abiertas:
            raise ErrorObservacionPendiente(
                f"La cuenta {cuenta_medica_id} tiene observaciones sin responder."
            )

        estado_actual = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        estado_nuevo = validar_transicion(estado_actual, TipoTransicion.CIERRE)
        await self._estado_cuenta.fijar_estado(cuenta_medica_id, estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TipoTransicion.CIERRE.value,
                actor=actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
            )
        )
        return estado_nuevo


class SolicitarAnulacion:
    """CU-13, flujo alternativo: "el analista registra la solicitud con
    su motivo" -- no mueve el estado de la cuenta todavia, por eso no
    pasa por el motor (la transicion a ANULADA exige la aprobacion,
    RF-21)."""

    def __init__(
        self,
        repositorio: RepositorioSolicitudesAnulacion,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, motivo: str, actor: str) -> int:
        estado_actual = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        # Tabla 58: la anulacion se admite "desde un estado no terminal"
        # (RF-21) -- la aprobacion todavia no existe en esta solicitud,
        # asi que la transicion en si (que la exige) se valida recien
        # en ResolverSolicitudAnulacion; aqui solo se adelanta el
        # rechazo que no depende de ella (Tabla 69).
        if estado_actual is None or estado_actual in ESTADOS_TERMINALES:
            raise ErrorTransicionNoDefinida(
                f"No se puede solicitar la anulacion de la cuenta {cuenta_medica_id}: "
                f"su estado {estado_actual!r} no admite nuevas transiciones."
            )

        pendiente = await self._repositorio.obtener_pendiente_por_cuenta(cuenta_medica_id)
        if pendiente is not None:
            raise ErrorSolicitudAnulacionYaPendiente(
                f"La cuenta {cuenta_medica_id} ya tiene una solicitud de anulacion pendiente."
            )

        ahora = self._reloj.ahora()
        solicitud_id = await self._repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_medica_id,
                motivo=motivo,
                solicitado_por=actor,
                solicitado_en=ahora,
            )
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="ANULACION_SOLICITADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"solicitud_id": solicitud_id, "motivo": motivo},
            )
        )
        return solicitud_id


class ResolverSolicitudAnulacion:
    """CU-13, flujo alternativo: "el jefe de cuentas medicas la aprueba
    o la rechaza; con la aprobacion, la cuenta pasa a ANULADA; con el
    rechazo, conserva su estado" (RF-21)."""

    def __init__(
        self,
        repositorio: RepositorioSolicitudesAnulacion,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, solicitud_id: int, aprobada: bool, actor: str) -> str | None:
        solicitud = await self._repositorio.obtener(solicitud_id)
        if solicitud is None:
            raise ErrorSolicitudAnulacionInexistente(f"No existe la solicitud {solicitud_id}.")
        if solicitud.estado != EstadoSolicitudAnulacion.PENDIENTE:
            raise ErrorSolicitudAnulacionYaResuelta(
                f"La solicitud {solicitud_id} ya fue {solicitud.estado.value.lower()}."
            )

        ahora = self._reloj.ahora()
        await self._repositorio.resolver(solicitud_id, aprobada, actor, ahora)

        if not aprobada:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=solicitud.cuenta_medica_id,
                    tipo_evento="ANULACION_RECHAZADA",
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"solicitud_id": solicitud_id},
                )
            )
            return None

        estado_actual = await self._estado_cuenta.obtener_estado(solicitud.cuenta_medica_id)
        estado_nuevo = validar_transicion(
            estado_actual, TipoTransicion.ANULACION, aprobacion_anulacion=True
        )
        await self._estado_cuenta.fijar_estado(solicitud.cuenta_medica_id, estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=solicitud.cuenta_medica_id,
                tipo_evento=TipoTransicion.ANULACION.value,
                actor=actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
                datos={"solicitud_id": solicitud_id},
            )
        )
        return estado_nuevo


class ListarSolicitudesAnulacionPendientes:
    """La bandeja del jefe de cuentas medicas para CU-13: "el jefe
    aprueba o rechaza" exige poder ver que hay pendiente."""

    def __init__(self, repositorio: RepositorioSolicitudesAnulacion) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[SolicitudAnulacion]:
        return await self._repositorio.listar_pendientes()
