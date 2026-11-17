"""Monto presentado de cada cuenta: procedimientos mas productos de
farmacia. Formula no normativa, la misma del monto total de un lote
(`repositorio_lotes_consulta_sql`). Dos consultas de agregacion separadas
y no un unico join de las tres tablas, que multiplicaria las filas."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import ProcedimientoFacturadoModelo


async def montos_por_cuenta(sesion: AsyncSession, cuenta_ids: list[int]) -> dict[int, Decimal]:
    if not cuenta_ids:
        return {}

    procedimientos = await sesion.execute(
        sa.select(
            ProcedimientoFacturadoModelo.cuenta_id,
            sa.func.sum(
                ProcedimientoFacturadoModelo.cantidad * ProcedimientoFacturadoModelo.monto_unitario
            ),
        )
        .where(ProcedimientoFacturadoModelo.cuenta_id.in_(cuenta_ids))
        .group_by(ProcedimientoFacturadoModelo.cuenta_id)
    )
    productos = await sesion.execute(
        sa.select(
            ProductoFacturadoModelo.cuenta_medica_id,
            sa.func.sum(ProductoFacturadoModelo.monto_presentado),
        )
        .where(ProductoFacturadoModelo.cuenta_medica_id.in_(cuenta_ids))
        .group_by(ProductoFacturadoModelo.cuenta_medica_id)
    )
    montos_procedimientos = {fila[0]: fila[1] for fila in procedimientos.all()}
    montos_productos = {fila[0]: fila[1] for fila in productos.all()}
    return {
        cuenta_id: (montos_procedimientos.get(cuenta_id) or Decimal("0.00"))
        + (montos_productos.get(cuenta_id) or Decimal("0.00"))
        for cuenta_id in cuenta_ids
    }
