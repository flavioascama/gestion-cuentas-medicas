"""Errores del contexto de liquidacion y pago."""

from __future__ import annotations


class ErrorLiquidacionInexistente(Exception):
    """CU-12: no existe una liquidacion registrada para la cuenta sobre
    la que se quiere conciliar el pago."""


class ErrorPagoYaConciliado(Exception):
    """CU-12: no se puede conciliar el pago dos veces sobre la misma
    liquidacion."""
