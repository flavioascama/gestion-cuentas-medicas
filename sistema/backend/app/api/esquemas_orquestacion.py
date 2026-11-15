"""Esquemas Pydantic de /cuentas/{id}/rechazo y
/cuentas/{id}/correccion-reenvio (T-05)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.orquestacion.puertos import RechazoCuenta


class RechazoCuentaRespuesta(BaseModel):
    lote_id: int
    numero_lote: str
    motivo: str | None
    rechazado_en: datetime | None

    @staticmethod
    def desde_valor(valor: RechazoCuenta) -> RechazoCuentaRespuesta:
        return RechazoCuentaRespuesta(**campos(valor))


class SolicitudCorreccionReenvio(BaseModel):
    descripcion_correccion: str = Field(min_length=1, max_length=500)


class RespuestaCorreccionReenvio(BaseModel):
    estado_cuenta: str
