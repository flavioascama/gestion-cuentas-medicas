"""Casos de uso del motor de orquestacion que no pertenecen a ningun otro
contexto: la correccion de una cuenta rechazada por la IAFAS para su
reenvio (T-05, Tabla 58, fila 11 de la Tabla 66). Antes de la
verificacion de cumplimiento del 12 de noviembre, la transicion estaba
definida en el motor pero nada la invocaba: una cuenta RECHAZADA quedaba
detenida y solo podia anularse, contra el camino de excepcion del TO-BE
("se corrige la cuenta y se incluye en un lote nuevo", Seccion 5.2.2)."""

from __future__ import annotations

from app.dominio.orquestacion.errores import ErrorComprobanteDesfasado
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import (
    RechazoCuenta,
    RepositorioEstadoCuenta,
    RepositorioRechazoCuenta,
)
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.pse.puertos import RepositorioCotejoComprobante
from app.dominio.puertos_comunes import Evento, Observabilidad


class ObtenerRechazoCuenta:
    def __init__(self, repositorio: RepositorioRechazoCuenta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> RechazoCuenta | None:
        return await self._repositorio.obtener_ultimo_rechazo(cuenta_medica_id)


class CorregirCuentaRechazada:
    """T-05: RECHAZADA -> FACTURADA. El analista declara que corrigio la
    cuenta (la descripcion queda en el evento, como sustento); la cuenta
    vuelve a FACTURADA y el generador de lotes la toma de nuevo. La fecha
    del primer envio del comprobante no se toca: la protege el disparador
    de la Fase 7 (RF-06, RI-12). Si la correccion cambio lo facturado, antes
    hay que emitir el comprobante de reemplazo (2026-11-18)."""

    def __init__(
        self,
        estado_cuenta: RepositorioEstadoCuenta,
        rechazos: RepositorioRechazoCuenta,
        observabilidad: Observabilidad,
        cotejo: RepositorioCotejoComprobante | None = None,
    ) -> None:
        self._estado_cuenta = estado_cuenta
        self._rechazos = rechazos
        self._observabilidad = observabilidad
        self._cotejo = cotejo

    async def ejecutar(self, cuenta_medica_id: int, descripcion: str, actor: str) -> str:
        estado_actual = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        estado_nuevo = validar_transicion(estado_actual, TipoTransicion.CORRECCION_REENVIO)
        if self._cotejo is not None and (await self._cotejo.cotejar(cuenta_medica_id)).desfasado:
            raise ErrorComprobanteDesfasado()
        rechazo = await self._rechazos.obtener_ultimo_rechazo(cuenta_medica_id)
        await self._estado_cuenta.fijar_estado(cuenta_medica_id, estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TipoTransicion.CORRECCION_REENVIO.value,
                actor=actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
                datos={
                    "descripcion_correccion": descripcion,
                    "lote_rechazado_id": rechazo.lote_id if rechazo else None,
                },
            )
        )
        return estado_nuevo
