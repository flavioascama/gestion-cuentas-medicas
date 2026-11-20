"""Adaptador de RepositorioLiquidaciones (Seccion 5.2.4.1, Fase 28)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.liquidacion.valores import DatosNuevaLiquidacion, Liquidacion
from app.infraestructura.persistencia.modelos_liquidacion import LiquidacionModelo


def _a_valor(fila: LiquidacionModelo) -> Liquidacion:
    return Liquidacion(
        id=fila.id,
        cuenta_medica_id=fila.cuenta_medica_id,
        es_parcial=fila.es_parcial,
        monto_liquidado=fila.monto_liquidado,
        registrado_en=fila.registrado_en,
        monto_pagado=fila.monto_pagado,
        diferencia=fila.diferencia,
        conciliado_en=fila.conciliado_en,
    )


class RepositorioLiquidacionesSql(RepositorioLiquidaciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear(self, datos: DatosNuevaLiquidacion) -> int:
        fila = LiquidacionModelo(
            cuenta_medica_id=datos.cuenta_medica_id,
            es_parcial=datos.es_parcial,
            monto_liquidado=datos.monto_liquidado,
            registrado_en=datos.registrado_en,
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        return fila.id

    async def obtener_por_cuenta(self, cuenta_medica_id: int) -> Liquidacion | None:
        fila = (
            await self._sesion.execute(
                sa.select(LiquidacionModelo).where(
                    LiquidacionModelo.cuenta_medica_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()
        return None if fila is None else _a_valor(fila)

    async def conciliar(
        self,
        liquidacion_id: int,
        monto_pagado: Decimal,
        diferencia: Decimal,
        conciliado_en: datetime,
    ) -> None:
        await self._sesion.execute(
            sa.update(LiquidacionModelo)
            .where(LiquidacionModelo.id == liquidacion_id)
            .values(monto_pagado=monto_pagado, diferencia=diferencia, conciliado_en=conciliado_en)
        )

    async def registrar_pago_adicional(
        self, liquidacion_id: int, monto_pagado: Decimal, diferencia: Decimal
    ) -> None:
        await self._sesion.execute(
            sa.update(LiquidacionModelo)
            .where(LiquidacionModelo.id == liquidacion_id)
            .values(monto_pagado=monto_pagado, diferencia=diferencia)
        )
