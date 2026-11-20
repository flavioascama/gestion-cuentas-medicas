"""Monto de un comprobante de pago: valor de venta, IGV y total.

Son los mismos montos que el lote lleva en la tabla T1 (base imponible, IGV
y total facturado), calculados con la misma regla y a partir de los mismos
procedimientos, productos de farmacia y copagos, para que lo que la cuenta
muestra como facturado sea lo que despues se le presenta a la IAFAS
(2026-11-18: el comprobante no guardaba ni mostraba ningun monto, y luego
no cobraba la farmacia). Tambien coteja los montos guardados del
comprobante con los actuales, para detectar un comprobante desfasado."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dominio.pse.puertos import CotejoMontos, MontosComprobante, RepositorioCotejoComprobante
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
)
from app.infraestructura.persistencia.repositorio_lote_sql import (
    RepositorioLoteFacturacionSql,
    montos_guardados,
)
from app.infraestructura.tedef.generar_lote import TASA_IGV
from app.infraestructura.tedef.montos_lote import (
    GastosPrestacion,
    MontosFacturados,
    calcular_gastos,
    calcular_montos_facturados,
    copago_del_asegurado,
)


def a_montos_comprobante(montos: MontosFacturados) -> MontosComprobante:
    return MontosComprobante(
        valor_venta=montos.valor_venta, igv=montos.igv, total=montos.total_facturado
    )


async def cotejo_de_cuenta(sesion: AsyncSession, cuenta_id: int) -> CotejoMontos:
    """Sin montos guardados no se calculan los actuales: no hay con que
    compararlos."""
    documento = await sesion.scalar(
        sa.select(DocumentoFacturadorModelo).where(DocumentoFacturadorModelo.cuenta_id == cuenta_id)
    )
    guardados = montos_guardados(documento) if documento is not None else None
    if documento is None or guardados is None:
        return CotejoMontos(guardados=None, actuales=None)
    actuales = await montos_facturados_de_cuenta(sesion, cuenta_id, documento.tipo_documento_pago)
    return CotejoMontos(
        guardados=guardados,
        actuales=a_montos_comprobante(actuales) if actuales is not None else None,
    )


class RepositorioCotejoComprobanteSql(RepositorioCotejoComprobante):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def cotejar(self, cuenta_medica_id: int) -> CotejoMontos:
        return await cotejo_de_cuenta(self._sesion, cuenta_medica_id)


async def montos_facturados_de_cuenta(
    sesion: AsyncSession, cuenta_id: int, tipo_documento_pago: str
) -> MontosFacturados | None:
    """None si la cuenta no existe o aun no tiene acreditacion (de ella salen
    los copagos)."""
    gastos = await gastos_de_cuenta(sesion, cuenta_id)
    if gastos is None:
        return None
    return calcular_montos_facturados(tipo_documento_pago, gastos, TASA_IGV)


async def copago_asegurado_de_cuenta(sesion: AsyncSession, cuenta_id: int) -> Decimal | None:
    """El copago que corresponde al asegurado (2026-11-19), con el mismo
    calculo que el lote y el comprobante. None sin acreditacion."""
    gastos = await gastos_de_cuenta(sesion, cuenta_id)
    return copago_del_asegurado(gastos) if gastos is not None else None


async def gastos_de_cuenta(sesion: AsyncSession, cuenta_id: int) -> GastosPrestacion | None:
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
    return calcular_gastos(procedimientos, productos)
