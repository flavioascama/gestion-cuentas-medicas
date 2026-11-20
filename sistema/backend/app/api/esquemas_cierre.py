"""Esquemas Pydantic de /cuentas/{id}/cierre, /cuentas/{id}/anulacion y
/anulaciones (CU-13, RF-21, Fase 28)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.cierre.valores import SolicitudAnulacion


class RespuestaCierre(BaseModel):
    estado_cuenta: str


class SolicitudNuevaAnulacion(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class RespuestaSolicitudAnulacion(BaseModel):
    solicitud_id: int


class SolicitudResolucionAnulacion(BaseModel):
    aprobada: bool


class RespuestaResolucionAnulacion(BaseModel):
    estado_cuenta: str | None


class SolicitudAnulacionRespuesta(BaseModel):
    id: int
    cuenta_medica_id: int
    motivo: str
    estado: str
    solicitado_por: str
    solicitado_en: datetime
    resuelto_por: str | None
    resuelto_en: datetime | None
    identificacion_interna: str | None = None
    asegurado: str | None = None
    estado_cuenta: str | None = None
    comprobante: str | None = None
    nota_credito: str | None = None

    @staticmethod
    def desde_valor(valor: SolicitudAnulacion) -> SolicitudAnulacionRespuesta:
        return SolicitudAnulacionRespuesta(**campos(valor))
