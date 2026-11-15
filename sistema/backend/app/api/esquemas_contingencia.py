"""Esquemas Pydantic del modo de contingencia (RF-23, C-18)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.contingencia.valores import (
    RegistroContingencia,
    ResultadoValidacionManual,
    UltimaConsultaCobertura,
)


class DisponibilidadContingenciaRespuesta(BaseModel):
    habilitada: bool


class UltimaConsultaCoberturaRespuesta(BaseModel):
    resultado: str
    intentos: int
    solicitada_en: datetime
    actualizada_en: datetime
    mensaje: str | None

    @staticmethod
    def desde_valor(valor: UltimaConsultaCobertura) -> UltimaConsultaCoberturaRespuesta:
        return UltimaConsultaCoberturaRespuesta(
            resultado=valor.resultado.value,
            intentos=valor.intentos,
            solicitada_en=valor.solicitada_en,
            actualizada_en=valor.actualizada_en,
            mensaje=valor.mensaje,
        )


class SolicitudCoberturaContingencia(BaseModel):
    condicion_cobertura: str = Field(min_length=1, max_length=20)
    codigo_autorizacion: str = Field(min_length=1, max_length=20)
    tipo_documento_autorizacion: str = Field(min_length=1, max_length=2)
    codigo_asegurado: str = Field(min_length=1, max_length=20)
    tipo_afiliacion: str = Field(min_length=1, max_length=1)
    vigente_hasta: date | None = None
    sustento: str = Field(min_length=1, max_length=1000)


class RespuestaCoberturaContingencia(BaseModel):
    acreditacion_id: int


class SolicitudValidacionContingencia(BaseModel):
    resultado: ResultadoValidacionManual
    sustento: str = Field(min_length=1, max_length=1000)
    # Solo para VALIDADO: el `.S01` en base64 (JSON, sin multipart: el
    # backend no depende de python-multipart).
    nombre_s01: str | None = Field(default=None, max_length=200)
    contenido_s01_base64: str | None = None


class RespuestaValidacionContingencia(BaseModel):
    estado_lote: str


class RegistroContingenciaRespuesta(BaseModel):
    evento_id: str
    tipo_operacion: str
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    lote_id: int | None
    numero_lote: str | None
    resumen: str
    sustento: str
    registrado_por: str
    registrado_en: datetime
    estado_revision: str
    revisado_por: str | None
    revisado_en: datetime | None
    comentario_revision: str | None

    @staticmethod
    def desde_valor(valor: RegistroContingencia) -> RegistroContingenciaRespuesta:
        return RegistroContingenciaRespuesta(**campos(valor))


class SolicitudRevisionContingencia(BaseModel):
    conforme: bool
    comentario: str = Field(default="", max_length=500)
