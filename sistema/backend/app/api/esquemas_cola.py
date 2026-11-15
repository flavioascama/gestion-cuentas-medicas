"""Esquemas Pydantic de /trabajos (Fase 18)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.puertos_comunes import DetalleTrabajo


class DetalleTrabajoRespuesta(BaseModel):
    id: int
    tipo: str
    carga_util: dict[str, Any]
    estado: str
    intentos: int
    error: str | None
    creado_en: datetime
    actualizado_en: datetime

    @staticmethod
    def desde_valor(valor: DetalleTrabajo) -> DetalleTrabajoRespuesta:
        return DetalleTrabajoRespuesta(**campos(valor))
