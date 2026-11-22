"""El día del Perú: el servidor guarda instantes en UTC, pero "hoy" es el
día de Lima (UTC-5, sin horario de verano)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

ZONA_PERU = timezone(timedelta(hours=-5))


def fecha_peru(instante: datetime) -> date:
    """La fecha de Lima de un instante con zona horaria."""
    return instante.astimezone(ZONA_PERU).date()
