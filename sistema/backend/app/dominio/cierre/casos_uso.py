"""Casos de uso del contexto de cierre y anulacion de la cuenta medica:
CU-13, "cerrar o anular la cuenta medica" (Tabla 52). El cierre (T-12)
es responsabilidad del analista; la anulacion (T-13, RF-21) la solicita
el analista y la aprueba o rechaza el jefe de cuentas medicas -- dos
casos de uso separados por eso, `SolicitarAnulacion` y
`ResolverSolicitudAnulacion`, igual que CU-08/CU-09 se separaron en
`RegistrarObservacion`/`AsignarResponsableObservacion` (Fase 26)."""

from __future__ import annotations

from dataclasses import replace

from app.compartido.nombres_estados import nombre_estado
from app.dominio.cierre.errores import (
    ErrorAnulacionPropia,
    ErrorDiferenciaPendiente,
    ErrorMotivoRechazoRequerido,
    ErrorObservacionPendiente,
    ErrorSinLiquidacion,
    ErrorSolicitudAnulacionInexistente,
    ErrorSolicitudAnulacionYaPendiente,
    ErrorSolicitudAnulacionYaResuelta,
)
from app.dominio.cierre.puertos import RepositorioSolicitudesAnulacion
from app.dominio.cierre.valores import (
    CondicionesCierre,
    DatosNuevaSolicitudAnulacion,
    EstadoCierreCuenta,
    EstadoSolicitudAnulacion,
    SolicitudAnulacion,
)
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.observaciones.puertos import RepositorioObservaciones
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES, TipoTransicion
from app.dominio.pse.documentos import RepositorioDocumentosPago
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj


async def evaluar_cierre(
    liquidaciones: RepositorioLiquidaciones,
    observaciones: RepositorioObservaciones,
    cuenta_medica_id: int,
) -> CondicionesCierre:
    """La unica regla de lo que falta para cerrar: la usan el cierre y la
    consulta de la seccion de cierre."""
    liquidacion = await liquidaciones.obtener_por_cuenta(cuenta_medica_id)
    conciliado = liquidacion is not None and liquidacion.diferencia is not None
    diferencia = liquidacion.diferencia if liquidacion is not None else None
    abiertas = [
        o for o in await observaciones.listar_por_cuenta(cuenta_medica_id) if o.estado == "ABIERTA"
    ]
    return CondicionesCierre(
        pago_conciliado=conciliado,
        diferencia=diferencia if diferencia else None,
        observaciones_sin_responder=len(abiertas),
    )


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
        condiciones = await evaluar_cierre(
            self._liquidaciones, self._observaciones, cuenta_medica_id
        )
        if not condiciones.pago_conciliado:
            raise ErrorSinLiquidacion("La cuenta no tiene un pago conciliado todavía.")
        if condiciones.diferencia is not None:
            raise ErrorDiferenciaPendiente(
                "La cuenta tiene una diferencia de S/ "
                f"{abs(condiciones.diferencia):.2f} entre lo liquidado y lo pagado sin resolver."
            )
        if condiciones.observaciones_sin_responder:
            raise ErrorObservacionPendiente("La cuenta tiene observaciones sin responder.")

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
        if estado_actual is None:
            raise ErrorTransicionNoDefinida(
                "No se puede solicitar la anulación de una cuenta que todavía no se registró."
            )
        if estado_actual in ESTADOS_TERMINALES:
            raise ErrorTransicionNoDefinida(
                "La anulación no procede en una cuenta Cerrada o Anulada: "
                f"esta cuenta está {nombre_estado(estado_actual)}."
            )

        pendiente = await self._repositorio.obtener_pendiente_por_cuenta(cuenta_medica_id)
        if pendiente is not None:
            raise ErrorSolicitudAnulacionYaPendiente(
                "La cuenta ya tiene una solicitud de anulación pendiente."
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


def _validar_resolucion(
    solicitud: SolicitudAnulacion, aprobada: bool, actor: str, motivo: str | None
) -> str | None:
    """Devuelve el motivo sin espacios sobrantes, o None si no se escribio."""
    if solicitud.estado != EstadoSolicitudAnulacion.PENDIENTE:
        raise ErrorSolicitudAnulacionYaResuelta(
            f"La solicitud de anulación ya fue {solicitud.estado.value.lower()}."
        )
    if aprobada and solicitud.solicitado_por == actor:
        raise ErrorAnulacionPropia(
            "Quien solicitó la anulación no la aprueba: la aprueba otra persona."
        )
    limpio = (motivo or "").strip() or None
    if not aprobada and limpio is None:
        raise ErrorMotivoRechazoRequerido("Falta el motivo del rechazo.")
    return limpio


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

    async def ejecutar(
        self, solicitud_id: int, aprobada: bool, actor: str, motivo: str | None = None
    ) -> str | None:
        solicitud = await self._repositorio.obtener(solicitud_id)
        if solicitud is None:
            raise ErrorSolicitudAnulacionInexistente("No existe la solicitud de anulación.")
        motivo = _validar_resolucion(solicitud, aprobada, actor, motivo)

        ahora = self._reloj.ahora()
        await self._repositorio.resolver(solicitud_id, aprobada, actor, ahora, motivo)
        # El resultado se avisa a quien la pidio (avisos/destinatarios.py).
        datos: dict[str, object] = {
            "solicitud_id": solicitud_id,
            "solicitado_por": solicitud.solicitado_por,
        }
        if motivo is not None:
            datos["motivo"] = motivo

        if not aprobada:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=solicitud.cuenta_medica_id,
                    tipo_evento="ANULACION_RECHAZADA",
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos=datos,
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
                datos=datos,
            )
        )
        return estado_nuevo


class ConsultarCierreCuenta:
    """Lectura de la seccion de cierre y anulacion: lo que falta para cerrar
    (la misma regla de CerrarCuenta) y la solicitud de anulacion pendiente o
    la ultima resuelta."""

    def __init__(
        self,
        liquidaciones: RepositorioLiquidaciones,
        observaciones: RepositorioObservaciones,
        solicitudes: RepositorioSolicitudesAnulacion,
    ) -> None:
        self._liquidaciones = liquidaciones
        self._observaciones = observaciones
        self._solicitudes = solicitudes

    async def ejecutar(self, cuenta_medica_id: int) -> EstadoCierreCuenta:
        return EstadoCierreCuenta(
            condiciones=await evaluar_cierre(
                self._liquidaciones, self._observaciones, cuenta_medica_id
            ),
            ultima_solicitud=await self._solicitudes.obtener_ultima_por_cuenta(cuenta_medica_id),
        )


class ListarSolicitudesAnulacionPendientes:
    """La bandeja del jefe de cuentas medicas para CU-13: "el jefe
    aprueba o rechaza" exige poder ver que hay pendiente. Con
    `documentos` (2026-11-19) cada solicitud lleva el comprobante vigente
    y la nota de credito de la cuenta."""

    def __init__(
        self,
        repositorio: RepositorioSolicitudesAnulacion,
        documentos: RepositorioDocumentosPago | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._documentos = documentos

    async def ejecutar(self) -> list[SolicitudAnulacion]:
        solicitudes = await self._repositorio.listar_pendientes()
        if self._documentos is None:
            return solicitudes
        return [await self._con_documentos(s) for s in solicitudes]

    async def _con_documentos(self, solicitud: SolicitudAnulacion) -> SolicitudAnulacion:
        assert self._documentos is not None
        documentos = await self._documentos.documentos(solicitud.cuenta_medica_id)
        if documentos is None:
            return solicitud
        vigente, nota = documentos.vigente, documentos.nota
        credito = f"{nota.serie}-{nota.numero}" if nota is not None and nota.tipo == "C" else None
        return replace(
            solicitud, comprobante=f"{vigente.serie}-{vigente.numero}", nota_credito=credito
        )
