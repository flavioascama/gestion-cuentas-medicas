"""Texto para el usuario cuando la cuenta no admite una operación en su estado."""

from __future__ import annotations

import re

from app.compartido.nombres_estados import nombre_estado
from app.infraestructura.observabilidad.registro import obtener_registrador

_registrador = obtener_registrador("api.errores")


def mensaje_operacion_no_disponible(error: Exception, *, ultimo: bool = False) -> str:
    """El detalle técnico queda en el registro del servidor."""
    _registrador.warning("transicion_rechazada", detalle=str(error))
    estados = [e for e in re.findall(r"[A-Z][A-Z_]+", str(error)) if nombre_estado(e) != e]
    base = "Esta operación no está disponible en el estado actual de la cuenta"
    if not estados:
        return f"{base}."
    return f"{base} ({nombre_estado(estados[-1] if ultimo else estados[0])})."
