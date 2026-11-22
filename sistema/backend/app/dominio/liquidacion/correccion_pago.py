"""Correccion del pago registrado a mano (auditoria final, 2026-11-21): un
pago mal digitado dejaba la cuenta con una diferencia sin forma de
regularizarla. Como la correccion de la liquidacion, solo el que registro
una persona, mientras la cuenta no este Cerrada ni Anulada; no cambia el
estado y queda como un evento nuevo con el monto anterior y el nuevo."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.dominio.liquidacion.casos_uso import motivo_pago_no_corregible
from app.dominio.liquidacion.errores import (
    ErrorLiquidacionInexistente,
    ErrorPagoExcedeLiquidado,
    ErrorPagoNoCorregible,
)
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.liquidacion.valores import Liquidacion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, Observabilidad

TIPO_EVENTO_PAGO_CORREGIDO = "PAGO_CORREGIDO"


class CorregirPago:
    """El monto corregido reemplaza lo pagado y no supera lo liquidado."""

    def __init__(
        self,
        repositorio: RepositorioLiquidaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad

    async def ejecutar(
        self, cuenta_medica_id: int, monto_pagado: Decimal, actor: str
    ) -> Liquidacion:
        liquidacion = await self._repositorio.obtener_por_cuenta(cuenta_medica_id)
        if liquidacion is None:
            raise ErrorLiquidacionInexistente("La cuenta no tiene una liquidación registrada.")
        motivo = await motivo_pago_no_corregible(
            self._repositorio, self._estado_cuenta, liquidacion
        )
        if motivo is not None:
            raise ErrorPagoNoCorregible(motivo)
        if monto_pagado > liquidacion.monto_liquidado:
            raise ErrorPagoExcedeLiquidado(monto_pagado, liquidacion.monto_liquidado)
        diferencia = monto_pagado - liquidacion.monto_liquidado
        await self._repositorio.registrar_pago_adicional(liquidacion.id, monto_pagado, diferencia)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_PAGO_CORREGIDO,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "liquidacion_id": liquidacion.id,
                    "monto_anterior": str(liquidacion.monto_pagado),
                    "monto_nuevo": str(monto_pagado),
                },
            )
        )
        return replace(liquidacion, monto_pagado=monto_pagado, diferencia=diferencia)
