"""Lo que se le cobra a la IAFAS por un comprobante (2026-11-22): su total
menos la nota de credito, o mas la nota de debito. La nota se registra sin
IGV y el total del comprobante lo incluye: la nota se lleva a la misma base
con la tasa del propio comprobante. Separado de documentos.py por el limite
de lineas por archivo."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.dominio.pse.documentos import DocumentosPagoCuenta

_CENTIMOS = Decimal("0.01")


def ajuste_de_nota(
    tipo: str, monto: Decimal, valor_venta: Decimal | None, igv: Decimal | None
) -> Decimal:
    """Lo que la nota cambia de lo que se cobra, con IGV y con su signo:
    negativo la de credito, positivo la de debito."""
    tasa = igv / valor_venta if valor_venta and igv else Decimal(0)
    con_igv = (monto * (1 + tasa)).quantize(_CENTIMOS, rounding=ROUND_HALF_UP)
    return -con_igv if tipo == "C" else con_igv


def neto_a_cobrar(documentos: DocumentosPagoCuenta) -> Decimal | None:
    vigente, nota = documentos.vigente, documentos.nota
    if vigente.total is None or nota is None:
        return vigente.total
    return vigente.total + ajuste_de_nota(nota.tipo, nota.monto, vigente.valor_venta, vigente.igv)
