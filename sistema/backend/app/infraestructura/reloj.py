"""Adaptador del puerto Reloj (app/dominio/puertos_comunes.py)."""

from __future__ import annotations

from datetime import UTC, datetime


class RelojSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)
