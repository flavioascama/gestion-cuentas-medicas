"""Esquema Pydantic de /avisos."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.avisos.valores import Aviso


class AvisoRespuesta(BaseModel):
    evento_id: str
    tipo_evento: str
    titulo: str
    severidad: str
    ocurrido_en: datetime
    datos: dict[str, Any]
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    lote_id: int | None
    numero_lote: str | None
    atendido: bool
    repeticiones: int

    @staticmethod
    def desde_valor(valor: Aviso) -> AvisoRespuesta:
        return AvisoRespuesta(**campos(valor))
