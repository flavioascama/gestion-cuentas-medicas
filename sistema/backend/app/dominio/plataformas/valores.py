"""DTOs del contexto de sesiones asistidas (Seccion 6.1, 8.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

PLATAFORMAS_VALIDAS = ("acredita_salud", "tedef_web")


@dataclass(frozen=True, slots=True)
class SesionPlataforma:
    """Fila de `sesion_plataforma` (Seccion 10): estado del protocolo de
    ingreso asistido con CAPTCHA para una plataforma externa."""

    id: int
    plataforma: str
    estado: str
    solicitada_por: str
    creada_en: datetime
    imagen_captcha: bytes | None
    respuesta_captcha: str | None
    activa_desde: datetime | None
    expira_en: datetime | None
    intentos: int
    motivo: str | None
