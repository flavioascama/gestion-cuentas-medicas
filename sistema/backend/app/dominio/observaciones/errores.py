"""Errores del contexto de observaciones/glosas."""

from __future__ import annotations


class ErrorMotivoInexistente(Exception):
    """CU-08: el codigo de motivo no existe en el catalogo vigente."""


class ErrorObservacionInexistente(Exception):
    """CU-09/CU-10: no existe la observacion sobre la que se quiere
    reasignar o responder."""


class ErrorResponsableNoValido(Exception):
    """CU-09: la persona elegida no existe, no esta activa o no tiene el
    rol que responde esa naturaleza de observacion."""


class ErrorObservacionYaRespondida(Exception):
    """CU-10: no se puede responder dos veces la misma observacion (una
    nueva objecion de la aseguradora sobre la respuesta es una
    observacion nueva, T-09, no una segunda respuesta a la misma)."""
