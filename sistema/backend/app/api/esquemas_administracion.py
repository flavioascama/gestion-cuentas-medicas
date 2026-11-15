"""Esquemas Pydantic de /catalogo-gtin (Fase 19)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.farmacia.puertos import VersionCatalogoGtin


class VersionCatalogoGtinRespuesta(BaseModel):
    id: int
    ruta_origen: str
    conteo: int
    cargado_en: datetime

    @staticmethod
    def desde_valor(valor: VersionCatalogoGtin) -> VersionCatalogoGtinRespuesta:
        return VersionCatalogoGtinRespuesta(**campos(valor))
