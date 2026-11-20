"""Esquemas Pydantic de /trabajos (Fase 18)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.puertos_comunes import DetalleTrabajo


class DetalleTrabajoRespuesta(BaseModel):
    id: int
    tipo: str
    estado: str
    intentos: int
    error: str | None
    creado_en: datetime
    actualizado_en: datetime

    @staticmethod
    def desde_valor(valor: DetalleTrabajo) -> DetalleTrabajoRespuesta:
        # Sin la carga util: puede traer texto de una respuesta a una glosa.
        datos = campos(valor)
        datos.pop("carga_util", None)
        return DetalleTrabajoRespuesta(**datos)
