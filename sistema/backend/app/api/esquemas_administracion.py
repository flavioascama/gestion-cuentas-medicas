"""Esquemas Pydantic de /catalogo-gtin (Fase 19)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.farmacia.puertos import VersionCatalogoGtin


class SolicitudCargarCatalogoGtin(BaseModel):
    nombre_archivo: str
    contenido_base64: str


class VersionCatalogoGtinRespuesta(BaseModel):
    id: int
    ruta_origen: str
    conteo: int
    cargado_en: datetime

    @staticmethod
    def desde_valor(valor: VersionCatalogoGtin) -> VersionCatalogoGtinRespuesta:
        return VersionCatalogoGtinRespuesta(**campos(valor))
