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

    async def actor_del_registro(self, liquidacion: Liquidacion) -> str | None:
        """Quien registro la liquidacion, segun su evento de registro en el
        historial (T-10); None si no hay evento."""
        ...

    async def total_facturado(self, cuenta_medica_id: int) -> Decimal | None:
        """Total del comprobante vigente de la cuenta (el que muestra la
        seccion de liquidacion); None si no se conoce."""
        ...

    async def actores_del_pago(self, liquidacion: Liquidacion) -> list[str | None]:
        """Quienes registraron los pagos de la liquidacion, segun sus eventos
        de conciliacion y de pago adicional en el historial."""
        ...

    async def corregir_monto(self, liquidacion_id: int, monto_liquidado: Decimal) -> None:
        """Reemplaza el monto liquidado de una liquidacion aun sin pago."""
        ...

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
        adicional o su correccion; la fecha de conciliacion sigue siendo la
        del primero."""
        ...
