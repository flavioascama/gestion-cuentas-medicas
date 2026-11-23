"""El documento que la persona adjunta al responder una observacion de la
IAFAS (2026-11-22): un PDF que viaja con la respuesta al portal de la
aseguradora. Puede traer datos del asegurado: se guarda cifrado (C-05)."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

TAMANO_MAXIMO_ADJUNTO = 5 * 1024 * 1024
LONGITUD_MAXIMA_NOMBRE = 200


class ErrorAdjuntoNoValido(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AdjuntoRespuesta:
    nombre: str
    contenido: bytes


def leer_adjunto(nombre: str, contenido_base64: str) -> AdjuntoRespuesta:
    """El adjunto de la solicitud, ya validado."""
    try:
        contenido = base64.b64decode(contenido_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ErrorAdjuntoNoValido("El documento adjunto no se pudo leer.") from error
    if not nombre.lower().endswith(".pdf") or not contenido.startswith(b"%PDF"):
        raise ErrorAdjuntoNoValido("El documento adjunto debe ser un archivo PDF.")
    if len(contenido) > TAMANO_MAXIMO_ADJUNTO:
        raise ErrorAdjuntoNoValido("El documento adjunto supera los 5 MB.")
    return AdjuntoRespuesta(nombre[:LONGITUD_MAXIMA_NOMBRE], contenido)
