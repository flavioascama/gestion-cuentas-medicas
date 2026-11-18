"""Monto de un comprobante de pago: valor de venta, IGV y total.

Son los mismos montos que el lote lleva en la tabla T1 (base imponible, IGV
y total facturado), calculados con la misma regla y a partir de los mismos
procedimientos, productos de farmacia y copagos, para que lo que la cuenta
muestra como facturado sea lo que despues se le presenta a la IAFAS
(2026-11-18: el comprobante no guardaba ni mostraba ningun monto, y luego
no cobraba la farmacia)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.tedef.generar_lote import TASA_IGV
from app.infraestructura.tedef.montos_lote import (
    MontosFacturados,
    calcular_gastos,
    calcular_montos_facturados,
)


async def montos_facturados_de_cuenta(
    sesion: AsyncSession, cuenta_id: int, tipo_documento_pago: str
) -> MontosFacturados | None:
    """None si la cuenta no existe o aun no tiene acreditacion (de ella salen
    los copagos)."""
    cuenta = (
        await sesion.execute(
            sa.select(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_id)
            .options(
                selectinload(CuentaMedicaModelo.acreditacion),
                selectinload(CuentaMedicaModelo.procedimientos),
            )
        )
    ).scalar_one_or_none()
    if cuenta is None or cuenta.acreditacion is None:
        return None
    ordenados = sorted(cuenta.procedimientos, key=lambda procedimiento: procedimiento.id)
    procedimientos = tuple(
        RepositorioLoteFacturacionSql._a_procedimiento_lote(  # noqa: SLF001 -- misma conversion del lote
            indice + 1, procedimiento, cuenta.acreditacion, es_el_primero=indice == 0
        )
        for indice, procedimiento in enumerate(ordenados)
    )
    filas = await sesion.execute(
        sa.select(ProductoFacturadoModelo)
        .where(ProductoFacturadoModelo.cuenta_medica_id == cuenta_id)
        .order_by(ProductoFacturadoModelo.correlativo)
    )
    productos = tuple(
        RepositorioLoteFacturacionSql._a_producto_lote(producto, cuenta.acreditacion)  # noqa: SLF001
        for producto in filas.scalars().all()
    )
    gastos = calcular_gastos(procedimientos, productos)
    return calcular_montos_facturados(tipo_documento_pago, gastos, TASA_IGV)
