"""Esquemas Pydantic de /cuentas/{id}/liquidacion y /cuentas/{id}/pago
(CU-12, Fase 28)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.liquidacion.valores import (
    Liquidacion,
    ResultadoConciliacion,
    ResultadoLiquidacion,
)


class SolicitudRegistroLiquidacion(BaseModel):
    monto_liquidado: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class SolicitudConciliacionPago(BaseModel):
    monto_pagado: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class RespuestaLiquidacionRegistrada(BaseModel):
    liquidacion_id: int
    estado_cuenta: str

    @staticmethod
    def desde_valor(valor: ResultadoLiquidacion) -> RespuestaLiquidacionRegistrada:
        return RespuestaLiquidacionRegistrada(**campos(valor))


class RespuestaConciliacion(BaseModel):
    estado_cuenta: str
    diferencia: Decimal

    @staticmethod
    def desde_valor(valor: ResultadoConciliacion) -> RespuestaConciliacion:
        return RespuestaConciliacion(**campos(valor))


class LiquidacionRespuesta(BaseModel):
    id: int
    cuenta_medica_id: int
    es_parcial: bool
    monto_liquidado: Decimal
    registrado_en: datetime
    monto_pagado: Decimal | None
    diferencia: Decimal | None
    conciliado_en: datetime | None

    @staticmethod
    def desde_valor(valor: Liquidacion) -> LiquidacionRespuesta:
        return LiquidacionRespuesta(**campos(valor))
