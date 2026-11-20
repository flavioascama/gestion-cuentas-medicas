"""Casos de uso del contexto de liquidacion y pago: CU-12, "la tesoreria
registra el monto liquidado y la cuenta pasa a LIQUIDADA o LIQUIDADA_
PARCIAL; al recibir el pago, registra el monto y su correspondencia con
la liquidacion, y el sistema concilia y lleva la cuenta a PAGADA o
PAGADA_PARCIAL" (Tabla 51)."""

from __future__ import annotations

from decimal import Decimal

from app.dominio.liquidacion.errores import (
    ErrorLiquidacionInexistente,
    ErrorPagoExcedeSaldo,
    ErrorPagoYaConciliado,
)
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.liquidacion.valores import (
    DatosNuevaLiquidacion,
    Liquidacion,
    ResultadoConciliacion,
    ResultadoLiquidacion,
)
from app.dominio.observaciones.puertos import RepositorioObservaciones
from app.dominio.observaciones.valores import ResultadoObservacion
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

# Una cuenta pagada de menos recibe pagos adicionales sin transicion: la
# Tabla 58 no define una y el estado ya es PAGADA o PAGADA_PARCIAL.
_ESTADOS_PAGADOS = frozenset({"PAGADA", "PAGADA_PARCIAL"})
TIPO_EVENTO_PAGO_ADICIONAL = "PAGO_ADICIONAL_REGISTRADO"


def _transicion_de_liquidacion(estado_actual: str | None) -> TipoTransicion:
    """Tabla 58: T-10 es LIQUIDACION_PARCIAL solo desde GLOSADA_PARCIAL
    (fila 13); desde EN_AUDITORIA o SUBSANADA (filas 5a y 7) es
    LIQUIDACION total. Fuera de esos tres estados, se devuelve
    LIQUIDACION igual: el motor es quien debe rechazarla."""

    if estado_actual == "GLOSADA_PARCIAL":
        return TipoTransicion.LIQUIDACION_PARCIAL
    return TipoTransicion.LIQUIDACION


def _transicion_de_conciliacion(estado_actual: str | None) -> TipoTransicion:
    """Tabla 58: T-11 es CONCILIACION_PAGO_PARCIAL solo desde LIQUIDADA_
    PARCIAL (fila 15); desde LIQUIDADA (filas 8) es CONCILIACION_PAGO."""

    if estado_actual == "LIQUIDADA_PARCIAL":
        return TipoTransicion.CONCILIACION_PAGO_PARCIAL
    return TipoTransicion.CONCILIACION_PAGO


class RegistrarLiquidacion:
    """CU-12, T-10 (RF-08, RF-12, RF-16). Con `observaciones`
    (2026-11-19): la liquidacion de una cuenta SUBSANADA es la aseguradora
    aceptando lo respondido, y esas observaciones quedan LEVANTADA. Desde
    GLOSADA_PARCIAL no se fija resultado: la liquidacion parcial no dice si
    se acepto la respuesta."""

    def __init__(
        self,
        repositorio: RepositorioLiquidaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
        observaciones: RepositorioObservaciones | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._observaciones = observaciones

    async def ejecutar(
        self, cuenta_medica_id: int, monto_liquidado: Decimal, actor: str
    ) -> ResultadoLiquidacion:
        estado_actual = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        transicion = _transicion_de_liquidacion(estado_actual)
        estado_nuevo = validar_transicion(estado_actual, transicion)

        ahora = self._reloj.ahora()
        liquidacion_id = await self._repositorio.crear(
            DatosNuevaLiquidacion(
                cuenta_medica_id=cuenta_medica_id,
                es_parcial=transicion is TipoTransicion.LIQUIDACION_PARCIAL,
                monto_liquidado=monto_liquidado,
                registrado_en=ahora,
            )
        )
        await self._estado_cuenta.fijar_estado(cuenta_medica_id, estado_nuevo)
        if estado_actual == "SUBSANADA" and self._observaciones is not None:
            await self._observaciones.fijar_resultado(
                cuenta_medica_id, ResultadoObservacion.LEVANTADA, ahora
            )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=transicion.value,
                actor=actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
                datos={"liquidacion_id": liquidacion_id, "monto_liquidado": str(monto_liquidado)},
            )
        )
        return ResultadoLiquidacion(liquidacion_id=liquidacion_id, estado_cuenta=estado_nuevo)


class ConciliarPago:
    """CU-12, T-11 (RF-08, RF-12, RF-16): "si el pago difiere del monto
    liquidado, el sistema registra la diferencia y la incorpora al
    seguimiento de la cartera por cobrar" (Tabla 51) -- la conciliacion
    avanza igual, la diferencia solo queda registrada para el
    seguimiento posterior (R3.4); quien bloquea el cierre ante una
    diferencia pendiente es CerrarCuenta, no este caso de uso. Mientras
    la cuenta pagada tenga saldo por pagar, admite pagos adicionales que
    se acumulan hasta cerrar la diferencia."""

    def __init__(
        self,
        repositorio: RepositorioLiquidaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(
        self, cuenta_medica_id: int, monto_pagado: Decimal, actor: str
    ) -> ResultadoConciliacion:
        liquidacion = await self._repositorio.obtener_por_cuenta(cuenta_medica_id)
        if liquidacion is None:
            raise ErrorLiquidacionInexistente(
                f"La cuenta {cuenta_medica_id} no tiene una liquidacion registrada."
            )
        estado_actual = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if liquidacion.conciliado_en is not None:
            return await self._pago_adicional(liquidacion, estado_actual, monto_pagado, actor)

        transicion = _transicion_de_conciliacion(estado_actual)
        estado_nuevo = validar_transicion(estado_actual, transicion)

        ahora = self._reloj.ahora()
        diferencia = monto_pagado - liquidacion.monto_liquidado
        await self._repositorio.conciliar(liquidacion.id, monto_pagado, diferencia, ahora)
        await self._estado_cuenta.fijar_estado(cuenta_medica_id, estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=transicion.value,
                actor=actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
                datos={
                    "liquidacion_id": liquidacion.id,
                    "monto_pagado": str(monto_pagado),
                    "diferencia": str(diferencia),
                },
            )
        )
        return ResultadoConciliacion(estado_cuenta=estado_nuevo, diferencia=diferencia)

    async def _pago_adicional(
        self, liquidacion: Liquidacion, estado_actual: str | None, monto: Decimal, actor: str
    ) -> ResultadoConciliacion:
        pagado_previo = liquidacion.monto_pagado or Decimal("0")
        if (
            estado_actual is None
            or estado_actual not in _ESTADOS_PAGADOS
            or pagado_previo >= liquidacion.monto_liquidado
        ):
            raise ErrorPagoYaConciliado(
                f"La liquidacion de la cuenta {liquidacion.cuenta_medica_id} ya tiene un "
                "pago conciliado."
            )
        saldo = liquidacion.monto_liquidado - pagado_previo
        if monto > saldo:
            raise ErrorPagoExcedeSaldo(
                f"El pago supera lo que falta por pagar de la cuenta "
                f"{liquidacion.cuenta_medica_id} ({saldo})."
            )
        acumulado = pagado_previo + monto
        diferencia = acumulado - liquidacion.monto_liquidado
        await self._repositorio.registrar_pago_adicional(liquidacion.id, acumulado, diferencia)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=liquidacion.cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_PAGO_ADICIONAL,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "liquidacion_id": liquidacion.id,
                    "monto_pago": str(monto),
                    "monto_pagado_acumulado": str(acumulado),
                    "diferencia": str(diferencia),
                },
            )
        )
        return ResultadoConciliacion(estado_cuenta=estado_actual, diferencia=diferencia)


class ObtenerLiquidacion:
    """Consulta de solo lectura (Seccion 5.2: "ninguna regla de negocio
    en una ruta" tambien cubre una consulta directa)."""

    def __init__(self, repositorio: RepositorioLiquidaciones) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> Liquidacion | None:
        return await self._repositorio.obtener_por_cuenta(cuenta_medica_id)
