"""Esquemas Pydantic de /comunicaciones-iafas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.comunicaciones.casos_uso import ComunicacionRegistrada


class ComunicacionIafasRespuesta(BaseModel):
    codigo: str
    canal: str
    tipo: str
    codigo_iafas: str
    codigo_ipress: str
    documento: str
    datos: dict[str, Any]
    emitida_en: str
    cuenta_medica_id: int | None
    resultado: str
    detalle: str | None
    observacion_id: int | None
    recibida_en: datetime
    respuesta_remitida_en: datetime | None

    @staticmethod
    def desde_valor(valor: ComunicacionRegistrada) -> ComunicacionIafasRespuesta:
        return ComunicacionIafasRespuesta(**campos(valor))


class RevisionSolicitada(BaseModel):
    trabajo_id: int
