"""Errores del contexto de observaciones/glosas."""

from __future__ import annotations

from decimal import Decimal


class ErrorMotivoInexistente(Exception):
    """CU-08: el codigo de motivo no existe en el catalogo vigente."""


class ErrorObservacionInexistente(Exception):
    """CU-09/CU-10: no existe la observacion sobre la que se quiere
    reasignar o responder."""


class ErrorResponsableNoValido(Exception):
    """CU-09: la persona elegida no existe, no esta activa o no tiene el
    rol que responde esa naturaleza de observacion."""


class ErrorObservacionDeOtroResponsable(Exception):
    """CU-10: la observacion tiene responsable asignado y solo esa persona
    la responde (2026-11-19)."""


class ErrorObservacionYaRespondida(Exception):
    """CU-10: no se puede responder dos veces la misma observacion (una
    nueva objecion de la aseguradora sobre la respuesta es una
    observacion nueva, T-09, no una segunda respuesta a la misma)."""


class ErrorMontoObservadoExcedeFacturado(Exception):
    """CU-08: el monto observado no supera el total facturado de la cuenta
    (auditoria final, 2026-11-21)."""

    def __init__(self, monto: Decimal, facturado: Decimal) -> None:
        super().__init__(
            f"El monto observado (S/ {monto:,.2f}) supera el total facturado de la cuenta "
            f"(S/ {facturado:,.2f})."
        )


class ErrorMontoObservadoNoValido(Exception):
    """CU-08: el monto observado es mayor que 0, y el de una glosa parcial,
    menor que el total facturado (segunda auditoria, 2026-11-21)."""


class ErrorRespuestaConComprobanteDesfasado(Exception):
    """CU-10: la respuesta no sale mientras el comprobante vigente no
    refleje la cuenta (la misma regla del reenvio de una cuenta rechazada)."""

    def __init__(self) -> None:
        super().__init__(
            "El comprobante ya no coincide con la cuenta: emita primero el comprobante de "
            "reemplazo y luego responda la observación."
        )
