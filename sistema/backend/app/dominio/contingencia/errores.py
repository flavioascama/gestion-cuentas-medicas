"""Errores del modo de contingencia (RF-23, C-18)."""

from __future__ import annotations


class ErrorContingencia(Exception):
    pass


class ErrorContingenciaNoHabilitada(ErrorContingencia):
    """La plataforma no se dio por no disponible: no hay una solicitud de
    esa operacion que haya agotado sus reintentos, o la operacion ya no
    corresponde (la cuenta ya tiene acreditacion, el lote ya se valido)."""


class ErrorSustentoInsuficiente(ErrorContingencia):
    """C-18: el registro en contingencia exige su sustento."""


class ErrorRegistroContingenciaInexistente(ErrorContingencia):
    pass


class ErrorRegistroContingenciaYaRevisado(ErrorContingencia):
    pass


class ErrorArchivoS01Invalido(ErrorContingencia):
    """El resultado VALIDADO en contingencia exige el `.S01` que entrego el
    validador por otro medio (RI-05: el sistema nunca lo genera)."""
