"""Esquemas Pydantic de /lotes (Fase 18)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.integracion.hallazgos import Hallazgo
from app.dominio.integracion.puertos_consulta import (
    CuentaDelLote,
    DetalleLote,
    InformePrevalidacionLote,
    ObservacionOficial,
    ResultadoValidacionOficial,
    ResumenAcuse,
    ResumenLote,
)
from app.infraestructura.tedef.generar_lote import ResultadoGenerarLote
from app.infraestructura.tedef.remitir_lote import ResultadoRemitirLote


class SolicitudGenerarLote(BaseModel):
    iafas_id: int
    periodo: str
    cuenta_ids: list[int]


class HallazgoRespuesta(BaseModel):
    severidad: str
    tabla: str
    campo_numero: int
    campo_nombre: str
    criterio_id: str
    criterio_texto: str
    valor: str
    mensaje: str

    @staticmethod
    def desde_valor(valor: Hallazgo) -> HallazgoRespuesta:
        return HallazgoRespuesta(**campos(valor))


class RespuestaGenerarLote(BaseModel):
    conforme: bool
    numero_lote: str
    hallazgos: list[HallazgoRespuesta]
    lote_id: int | None
    rutas_archivos: list[str] | None

    @staticmethod
    def desde_valor(valor: ResultadoGenerarLote) -> RespuestaGenerarLote:
        return RespuestaGenerarLote(
            conforme=valor.conforme,
            numero_lote=valor.informe.numero_lote,
            hallazgos=[HallazgoRespuesta.desde_valor(h) for h in valor.informe.hallazgos],
            lote_id=valor.lote_id,
            rutas_archivos=list(valor.rutas_archivos) if valor.rutas_archivos else None,
        )


class ResumenLoteRespuesta(BaseModel):
    id: int
    numero: str
    periodo: str
    iafas_codigo: str
    estado: str
    generado_en: datetime
    cantidad_documentos: int
    monto_total: Decimal
    monitoreo_excedido: bool

    @staticmethod
    def desde_valor(valor: ResumenLote) -> ResumenLoteRespuesta:
        return ResumenLoteRespuesta(**campos(valor))


class DetalleLoteRespuesta(BaseModel):
    id: int
    numero: str
    periodo: str
    iafas_codigo: str
    estado: str
    generado_en: datetime
    cantidad_documentos: int
    nombre_s01: str | None
    sha256_s01: str | None
    s01_obtenido_en: datetime | None
    enviado_susalud_en: datetime | None
    version_esquema_tedef: str | None
    version_mapeo: str | None
    monitoreo_excedido: bool

    @staticmethod
    def desde_valor(valor: DetalleLote) -> DetalleLoteRespuesta:
        return DetalleLoteRespuesta(**campos(valor))


class InformePrevalidacionRespuesta(BaseModel):
    conforme: bool
    generado_en: datetime
    hallazgos: list[HallazgoRespuesta]

    @staticmethod
    def desde_valor(valor: InformePrevalidacionLote) -> InformePrevalidacionRespuesta:
        return InformePrevalidacionRespuesta(
            conforme=valor.conforme,
            generado_en=valor.generado_en,
            hallazgos=[HallazgoRespuesta.desde_valor(h) for h in valor.hallazgos],
        )


class ObservacionOficialRespuesta(BaseModel):
    tabla: str | None
    numero_linea: int | None
    campo_clave: str | None
    campo: str | None
    valor_observado: str | None
    codigo_error: str
    descripcion: str

    @staticmethod
    def desde_valor(valor: ObservacionOficial) -> ObservacionOficialRespuesta:
        return ObservacionOficialRespuesta(**campos(valor))


class ResultadoValidacionOficialRespuesta(BaseModel):
    etapa: str
    resultado: str
    estado_informado_validador: str | None
    registrado_en: datetime
    observaciones: list[ObservacionOficialRespuesta]

    @staticmethod
    def desde_valor(valor: ResultadoValidacionOficial) -> ResultadoValidacionOficialRespuesta:
        return ResultadoValidacionOficialRespuesta(
            etapa=valor.etapa,
            resultado=valor.resultado,
            estado_informado_validador=valor.estado_informado_validador,
            registrado_en=valor.registrado_en,
            observaciones=[ObservacionOficialRespuesta.desde_valor(o) for o in valor.observaciones],
        )


class CuentaLoteRespuesta(BaseModel):
    id: int
    identificacion_interna: str
    nombres_asegurado: str
    apellidos_asegurado: str
    monto: Decimal
    estado: str
    fecha_prestacion: date | None

    @staticmethod
    def desde_valor(valor: CuentaDelLote) -> CuentaLoteRespuesta:
        return CuentaLoteRespuesta(**campos(valor))


class ResumenAcuseRespuesta(BaseModel):
    id: int
    resultado_transferencia: str
    motivo_transferencia: str | None
    intentado_en: datetime
    respuesta_receptor: str | None
    motivo_receptor: str | None
    respondido_en: datetime | None

    @staticmethod
    def desde_valor(valor: ResumenAcuse) -> ResumenAcuseRespuesta:
        return ResumenAcuseRespuesta(**campos(valor))


class RespuestaTrabajoEncolado(BaseModel):
    trabajo_id: int


class RespuestaRemitirLote(BaseModel):
    exitosa: bool
    lote_id: int
    acuse_id: int
    motivo: str | None

    @staticmethod
    def desde_valor(valor: ResultadoRemitirLote) -> RespuestaRemitirLote:
        return RespuestaRemitirLote(**campos(valor))


class SolicitudEnvioSusalud(BaseModel):
    periodo: str


class RespuestaEnvioSusalud(BaseModel):
    trabajo_id: int | None
