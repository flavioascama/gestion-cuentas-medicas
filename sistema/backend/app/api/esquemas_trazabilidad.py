"""Esquemas Pydantic de /cuentas/{id}/historial, /indicadores y
/cuentas/{id}/expediente (CU-14 a CU-16, Fase 29)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.trazabilidad.valores import (
    CicloCuenta,
    DistribucionEstado,
    DocumentoExpediente,
    EventoHistorial,
    Expediente,
    HistorialCuenta,
    HistorialLote,
    IndicadoresCiclo,
    IndicadoresIafas,
    LotesPeriodoEstado,
    TiempoCicloCuentas,
    TiempoEtapa,
)


class EventoHistorialRespuesta(BaseModel):
    tipo_evento: str
    actor: str
    estado_previo: str | None
    estado_nuevo: str | None
    ocurrido_en: datetime
    datos: dict[str, Any]

    @staticmethod
    def desde_valor(valor: EventoHistorial) -> EventoHistorialRespuesta:
        return EventoHistorialRespuesta(**campos(valor))


class HistorialCuentaRespuesta(BaseModel):
    cuenta_medica_id: int
    eventos: list[EventoHistorialRespuesta]
    cadena_integra: bool
    rupturas: list[str]

    @staticmethod
    def desde_valor(valor: HistorialCuenta) -> HistorialCuentaRespuesta:
        return HistorialCuentaRespuesta(
            cuenta_medica_id=valor.cuenta_medica_id,
            eventos=[EventoHistorialRespuesta.desde_valor(e) for e in valor.eventos],
            cadena_integra=valor.cadena_integra,
            rupturas=valor.rupturas,
        )


class HistorialLoteRespuesta(BaseModel):
    lote_id: int
    eventos: list[EventoHistorialRespuesta]
    cadena_integra: bool
    rupturas: list[str]

    @staticmethod
    def desde_valor(valor: HistorialLote) -> HistorialLoteRespuesta:
        return HistorialLoteRespuesta(
            lote_id=valor.lote_id,
            eventos=[EventoHistorialRespuesta.desde_valor(e) for e in valor.eventos],
            cadena_integra=valor.cadena_integra,
            rupturas=valor.rupturas,
        )


class TiempoEtapaRespuesta(BaseModel):
    etapa: str
    promedio_horas: float
    transiciones: int

    @staticmethod
    def desde_valor(valor: TiempoEtapa) -> TiempoEtapaRespuesta:
        return TiempoEtapaRespuesta(**campos(valor))


class DistribucionEstadoRespuesta(BaseModel):
    estado: str
    cantidad: int

    @staticmethod
    def desde_valor(valor: DistribucionEstado) -> DistribucionEstadoRespuesta:
        return DistribucionEstadoRespuesta(**campos(valor))


class LotesPeriodoEstadoRespuesta(BaseModel):
    periodo: str
    estado: str
    cantidad: int

    @staticmethod
    def desde_valor(valor: LotesPeriodoEstado) -> LotesPeriodoEstadoRespuesta:
        return LotesPeriodoEstadoRespuesta(**campos(valor))


class IndicadoresIafasRespuesta(BaseModel):
    iafas_codigo: str
    iafas_razon_social: str
    cuentas: int
    monto_registrado: Decimal
    cartera_por_cobrar: Decimal
    tasa_glosas: float
    lotes: int
    pct_lotes_observados: float

    @staticmethod
    def desde_valor(valor: IndicadoresIafas) -> IndicadoresIafasRespuesta:
        return IndicadoresIafasRespuesta(**campos(valor))


class CicloCuentaRespuesta(BaseModel):
    cuenta_medica_id: int
    identificacion_interna: str
    estado: str
    horas: float

    @staticmethod
    def desde_valor(valor: CicloCuenta) -> CicloCuentaRespuesta:
        return CicloCuentaRespuesta(**campos(valor))


class TiempoCicloCuentasRespuesta(BaseModel):
    cuentas_cerradas: int
    promedio_horas_cerradas: float | None
    mediana_horas_cerradas: float | None
    cuentas_abiertas: int
    promedio_horas_abiertas: float | None
    mas_antiguas_abiertas: list[CicloCuentaRespuesta]

    @staticmethod
    def desde_valor(valor: TiempoCicloCuentas) -> TiempoCicloCuentasRespuesta:
        return TiempoCicloCuentasRespuesta(
            cuentas_cerradas=valor.cuentas_cerradas,
            promedio_horas_cerradas=valor.promedio_horas_cerradas,
            mediana_horas_cerradas=valor.mediana_horas_cerradas,
            cuentas_abiertas=valor.cuentas_abiertas,
            promedio_horas_abiertas=valor.promedio_horas_abiertas,
            mas_antiguas_abiertas=[
                CicloCuentaRespuesta.desde_valor(c) for c in valor.mas_antiguas_abiertas
            ],
        )


class RegistrosContingenciaRespuesta(BaseModel):
    total: int
    pendientes_revision: int


class IndicadoresCicloRespuesta(BaseModel):
    tiempo_por_etapa: list[TiempoEtapaRespuesta]
    pct_lotes_observados: float
    pct_lotes_rechazados: float
    tasa_glosas: float
    distribucion_por_estado: list[DistribucionEstadoRespuesta]
    cartera_por_cobrar: Decimal
    lotes_evaluados: int
    cuentas_evaluadas: int
    lotes_por_periodo: list[LotesPeriodoEstadoRespuesta]
    por_iafas: list[IndicadoresIafasRespuesta]
    tiempo_ciclo_cuentas: TiempoCicloCuentasRespuesta
    registros_contingencia: RegistrosContingenciaRespuesta

    @staticmethod
    def desde_valor(valor: IndicadoresCiclo) -> IndicadoresCicloRespuesta:
        return IndicadoresCicloRespuesta(
            tiempo_por_etapa=[TiempoEtapaRespuesta.desde_valor(t) for t in valor.tiempo_por_etapa],
            pct_lotes_observados=valor.pct_lotes_observados,
            pct_lotes_rechazados=valor.pct_lotes_rechazados,
            tasa_glosas=valor.tasa_glosas,
            distribucion_por_estado=[
                DistribucionEstadoRespuesta.desde_valor(d) for d in valor.distribucion_por_estado
            ],
            cartera_por_cobrar=valor.cartera_por_cobrar,
            lotes_evaluados=valor.lotes_evaluados,
            cuentas_evaluadas=valor.cuentas_evaluadas,
            lotes_por_periodo=[
                LotesPeriodoEstadoRespuesta.desde_valor(f) for f in valor.lotes_por_periodo
            ],
            por_iafas=[IndicadoresIafasRespuesta.desde_valor(f) for f in valor.por_iafas],
            tiempo_ciclo_cuentas=TiempoCicloCuentasRespuesta.desde_valor(
                valor.tiempo_ciclo_cuentas
            ),
            registros_contingencia=RegistrosContingenciaRespuesta(
                total=valor.registros_contingencia.total,
                pendientes_revision=valor.registros_contingencia.pendientes_revision,
            ),
        )


class DocumentoExpedienteRespuesta(BaseModel):
    tipo: str
    referencia: str
    emitido_en: datetime | None
    fecha_emision: date | None = None

    @staticmethod
    def desde_valor(valor: DocumentoExpediente) -> DocumentoExpedienteRespuesta:
        return DocumentoExpedienteRespuesta(**campos(valor))


class SolicitudExportacionExpediente(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class ExpedienteRespuesta(BaseModel):
    cuenta_medica_id: int
    historial: HistorialCuentaRespuesta
    documentos: list[DocumentoExpedienteRespuesta]
    generado_en: datetime

    @staticmethod
    def desde_valor(valor: Expediente) -> ExpedienteRespuesta:
        return ExpedienteRespuesta(
            cuenta_medica_id=valor.cuenta_medica_id,
            historial=HistorialCuentaRespuesta.desde_valor(valor.historial),
            documentos=[DocumentoExpedienteRespuesta.desde_valor(d) for d in valor.documentos],
            generado_en=valor.generado_en,
        )
