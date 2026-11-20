"""Puerto del contexto de liquidacion y pago (Seccion 5.2.4.1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.dominio.liquidacion.valores import DatosNuevaLiquidacion, Liquidacion


class RepositorioLiquidaciones(Protocol):
    async def crear(self, datos: DatosNuevaLiquidacion) -> int:
        """Devuelve el id de la liquidacion creada (CU-12, T-10)."""
        ...

    async def obtener_por_cuenta(self, cuenta_medica_id: int) -> Liquidacion | None: ...

    async def conciliar(
        self,
        liquidacion_id: int,
        monto_pagado: Decimal,
        diferencia: Decimal,
        conciliado_en: datetime,
    ) -> None:
        """CU-12, T-11: completa la liquidacion con el pago recibido."""
        ...

    async def registrar_pago_adicional(
        self, liquidacion_id: int, monto_pagado: Decimal, diferencia: Decimal
    ) -> None:
        """Actualiza lo pagado (acumulado) y la diferencia tras un pago
        adicional; la fecha de conciliacion sigue siendo la del primero."""
        ...
