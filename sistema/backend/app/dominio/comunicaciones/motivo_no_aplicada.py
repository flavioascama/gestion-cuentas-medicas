"""Por que una comunicacion de la IAFAS no se aplico, en una frase para la
persona que la lee en la bandeja y en el aviso (no el texto de la
excepcion)."""

from __future__ import annotations

from app.compartido.nombres_estados import nombre_estado
from app.dominio.liquidacion.errores import ErrorMontoExcedido, ErrorPagoExcedeSaldo
from app.dominio.observaciones.conformidad import ErrorCuentaInexistenteAuditoria
from app.dominio.observaciones.errores import (
    ErrorMontoObservadoExcedeFacturado,
    ErrorMontoObservadoNoValido,
    ErrorMotivoInexistente,
)
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES

COMPROBANTE_NO_ENCONTRADO = "No se encontró el comprobante de la comunicación."
# Un monto por encima de su tope (auditoria final, 2026-11-21); el pago
# adicional excesivo ya entra como ErrorPagoYaConciliado.
RECHAZOS_POR_MONTO: tuple[type[Exception], ...] = (
    ErrorMontoExcedido,
    ErrorMontoObservadoExcedeFacturado,
    ErrorMontoObservadoNoValido,
)


def motivo_no_aplicada(error: Exception, estado_cuenta: str | None) -> str:
    if estado_cuenta in ESTADOS_TERMINALES:
        return f"La cuenta ya está {nombre_estado(estado_cuenta).lower()}."
    # Un monto por encima de su tope: el mensaje ya dice ambos montos.
    if isinstance(error, (*RECHAZOS_POR_MONTO, ErrorPagoExcedeSaldo)):
        return str(error)
    if isinstance(error, ErrorCuentaInexistenteAuditoria):
        return "No se encontró la cuenta de la comunicación."
    if isinstance(error, ErrorMotivoInexistente | ValueError | KeyError):
        return "Falta un dato en la comunicación o no es válido."
    if estado_cuenta is None:
        return "La comunicación no corresponde al estado actual de la cuenta."
    return (
        "La comunicación no corresponde al estado actual de la cuenta "
        f"({nombre_estado(estado_cuenta)})."
    )
