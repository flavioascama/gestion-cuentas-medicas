"""Errores del modulo de trazabilidad con panel de control gerencial."""

from __future__ import annotations


class ErrorCuentaInexistente(Exception):
    """CU-14/CU-16: no existe la cuenta sobre la que se quiere
    reconstruir el historial o exportar el expediente."""


class ErrorLoteInexistente(Exception):
    pass
