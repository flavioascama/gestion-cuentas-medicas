"""Lo facturado a la IAFAS por cada comprobante: el monto de un lote, el de
cada cuenta del lote y el de las cuentas por lotear (auditoria final,
hallazgo 4; hasta el 2026-11-21 era la suma de lo presentado)."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.infraestructura.persistencia.modelos_integracion import DocumentoFacturadorModelo
from app.infraestructura.persistencia.montos_comprobante_sql import montos_facturados_de_cuenta


async def facturado_por_documento(
    sesion: AsyncSession, documento_ids: list[int]
) -> dict[int, Decimal]:
    """Lo facturado a la IAFAS por cada comprobante: el total con IGV que
    guardo al emitirse (auditoria final, hallazgo 4). Un comprobante
    anterior al 2026-11-18 no guardo montos: se calcula con la misma regla
    del lote y del comprobante, y da 0.00 si la cuenta no tiene acreditacion."""
    if not documento_ids:
        return {}
    filas = await sesion.execute(
        sa.select(
            DocumentoFacturadorModelo.id,
            DocumentoFacturadorModelo.cuenta_id,
            DocumentoFacturadorModelo.tipo_documento_pago,
            DocumentoFacturadorModelo.total,
        ).where(DocumentoFacturadorModelo.id.in_(documento_ids))
    )
    facturado: dict[int, Decimal] = {}
    for documento_id, cuenta_id, tipo_documento_pago, total in filas.all():
        if total is None:
            montos = await montos_facturados_de_cuenta(sesion, cuenta_id, tipo_documento_pago)
            total = montos.total_facturado if montos is not None else Decimal("0.00")
        facturado[documento_id] = total
    return facturado


async def facturado_remitido(
    sesion: AsyncSession, enlaces: list[tuple[int, Decimal | None]]
) -> list[Decimal]:
    """Lo que un lote remitio por cada comprobante (documento, total
    guardado): el total guardado al generar el lote, que no cambia si despues
    se reemplaza el comprobante (segunda auditoria final, hallazgo 1). Un lote
    anterior no lo guardo: se usa el total actual del comprobante."""
    actual = await facturado_por_documento(
        sesion, [documento_id for documento_id, total in enlaces if total is None]
    )
    return [actual[d] if total is None else total for d, total in enlaces]
