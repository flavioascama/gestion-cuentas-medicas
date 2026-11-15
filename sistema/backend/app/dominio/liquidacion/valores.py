"""DTOs del contexto de liquidacion y pago (Seccion 5.2.4.1, Tabla 58
T-10/T-11; CU-12, Fase 28)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DatosNuevaLiquidacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) de
    `RepositorioLiquidaciones.crear`."""

    cuenta_medica_id: int
    es_parcial: bool
    monto_liquidado: Decimal
    registrado_en: datetime


@dataclass(frozen=True, slots=True)
class Liquidacion:
    """Entidad de dominio, tal como la devuelve el repositorio."""

    id: int
    cuenta_medica_id: int
    es_parcial: bool
    monto_liquidado: Decimal
    registrado_en: datetime
    monto_pagado: Decimal | None
    diferencia: Decimal | None
    conciliado_en: datetime | None


@dataclass(frozen=True, slots=True)
class ResultadoLiquidacion:
    liquidacion_id: int
    estado_cuenta: str


@dataclass(frozen=True, slots=True)
class ResultadoConciliacion:
    estado_cuenta: str
    diferencia: Decimal
