"""Hallazgo de validacion (Seccion 7.6): un error o una advertencia sobre
un campo concreto de un registro, con el criterio literal que lo origina.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severidad = Literal["error", "advertencia"]


@dataclass(frozen=True, slots=True)
class Hallazgo:
    severidad: Severidad
    tabla: str
    campo_numero: int
    campo_nombre: str
    criterio_id: str
    criterio_texto: str
    valor: str
    mensaje: str
