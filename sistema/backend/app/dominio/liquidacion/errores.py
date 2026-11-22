"""Errores del contexto de liquidacion y pago."""

from __future__ import annotations

from decimal import Decimal


class ErrorLiquidacionInexistente(Exception):
    """CU-12: no existe una liquidacion registrada para la cuenta sobre
    la que se quiere conciliar el pago."""


class ErrorLiquidacionNoCorregible(Exception):
    """La liquidacion solo se corrige mientras la cuenta siga en el estado
    en que quedo al liquidarse y sin ningun pago registrado."""


class ErrorPagoNoCorregible(Exception):
    """El pago solo se corrige si lo registro una persona y la cuenta no
    esta Cerrada ni Anulada (auditoria final, 2026-11-21)."""


class ErrorMontoExcedido(Exception):
    """Un monto supera su tope: la liquidacion, lo facturado; lo pagado, lo
    liquidado (auditoria final, 2026-11-21). El mensaje dice ambos montos."""


class ErrorLiquidacionExcedeFacturado(ErrorMontoExcedido):
    def __init__(self, monto: Decimal, facturado: Decimal) -> None:
        super().__init__(
            f"La liquidación (S/ {monto:,.2f}) supera el total facturado de la cuenta "
            f"(S/ {facturado:,.2f})."
        )


class ErrorPagoExcedeLiquidado(ErrorMontoExcedido):
    def __init__(self, monto: Decimal, liquidado: Decimal) -> None:
        super().__init__(
            f"El pago (S/ {monto:,.2f}) supera lo liquidado por la IAFAS (S/ {liquidado:,.2f})."
        )


class ErrorPagoYaConciliado(Exception):
    """CU-12: no se puede conciliar el pago dos veces sobre la misma
    liquidacion."""


class ErrorPagoExcedeSaldo(ErrorPagoYaConciliado):
    """Un pago adicional mayor que lo que falta por pagar dejaria la
    cuenta con una diferencia que ya no se puede regularizar. Hereda
    del error anterior para que quien ya lo maneja lo trate igual."""
