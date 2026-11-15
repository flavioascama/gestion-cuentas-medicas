"""Esquemas Pydantic de /plataformas (Fase 18)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.dominio.plataformas.valores import SesionPlataforma


class RespuestaSesionSolicitada(BaseModel):
    sesion_id: int


class SolicitudRespuestaCaptcha(BaseModel):
    respuesta: str


class ResumenSesionPlataformaRespuesta(BaseModel):
    id: int
    plataforma: str
    estado: str
    solicitada_por: str
    creada_en: datetime
    activa_desde: datetime | None
    expira_en: datetime | None
    intentos: int
    motivo: str | None

    @staticmethod
    def desde_valor(valor: SesionPlataforma) -> ResumenSesionPlataformaRespuesta:
        return ResumenSesionPlataformaRespuesta(
            id=valor.id,
            plataforma=valor.plataforma,
            estado=valor.estado,
            solicitada_por=valor.solicitada_por,
            creada_en=valor.creada_en,
            activa_desde=valor.activa_desde,
            expira_en=valor.expira_en,
            intentos=valor.intentos,
            motivo=valor.motivo,
        )
