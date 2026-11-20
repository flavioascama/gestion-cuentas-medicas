"""Esquemas Pydantic de /lotes (Fase 18)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.api.serializacion import campos
from app.dominio.integracion.hallazgos import Hallazgo
from app.dominio.integracion.lotes_sugeridos import CuentaPorLotear, LoteSugerido
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
    # Sin periodo, el lote toma el mes de emision de sus comprobantes.
    periodo: str | None = None
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


class PendientesCuentaRespuesta(BaseModel):
    """Una cuenta que impidio generar el lote y que le falta, en simple."""

    cuenta_id: int
    identificacion_interna: str
    pendientes: list[str]


class RespuestaGenerarLote(BaseModel):
    conforme: bool
    numero_lote: str
    hallazgos: list[HallazgoRespuesta]
    lote_id: int | None
    rutas_archivos: list[str] | None
    cuentas_con_pendientes: list[PendientesCuentaRespuesta] = []

    @staticmethod
    def desde_valor(valor: ResultadoGenerarLote) -> RespuestaGenerarLote:
        return RespuestaGenerarLote(
            conforme=valor.conforme,
            numero_lote=valor.informe.numero_lote,
            hallazgos=[HallazgoRespuesta.desde_valor(h) for h in valor.informe.hallazgos],
            lote_id=valor.lote_id,
            rutas_archivos=list(valor.rutas_archivos) if valor.rutas_archivos else None,
            cuentas_con_pendientes=[
                PendientesCuentaRespuesta(
                    cuenta_id=p.cuenta_medica_id,
                    identificacion_interna=p.identificacion_interna,
                    pendientes=list(p.pendientes),
                )
                for p in valor.pendientes
            ],
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
    validacion_reintentable: bool

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
    cuenta_medica_id: int | None = None
    identificacion_interna: str | None = None

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


class CuentaPorLotearRespuesta(BaseModel):
    cuenta_id: int
    identificacion_interna: str
    nombres_asegurado: str
    apellidos_asegurado: str
    fecha_emision: date
    monto: Decimal
    pendientes: list[str] = []

    @staticmethod
    def desde_valor(valor: CuentaPorLotear) -> CuentaPorLotearRespuesta:
        return CuentaPorLotearRespuesta(
            cuenta_id=valor.cuenta_id,
            identificacion_interna=valor.identificacion_interna,
            nombres_asegurado=valor.nombres_asegurado,
            apellidos_asegurado=valor.apellidos_asegurado,
            fecha_emision=valor.fecha_emision,
            monto=valor.monto,
            pendientes=list(valor.pendientes),
        )


class LoteSugeridoRespuesta(BaseModel):
    """Un grupo de cuentas facturadas de una IAFAS y un periodo (el mes de
    sus comprobantes), listo para generarse como lote."""

    iafas_id: int
    iafas_codigo: str
    iafas_razon_social: str
    periodo: str
    monto_total: Decimal
    cuentas: list[CuentaPorLotearRespuesta]
    cuentas_con_pendientes: list[CuentaPorLotearRespuesta] = []

    @staticmethod
    def desde_valor(valor: LoteSugerido) -> LoteSugeridoRespuesta:
        return LoteSugeridoRespuesta(
            iafas_id=valor.iafas_id,
            iafas_codigo=valor.iafas_codigo,
            iafas_razon_social=valor.iafas_razon_social,
            periodo=valor.periodo,
            monto_total=valor.monto_total,
            cuentas=[CuentaPorLotearRespuesta.desde_valor(c) for c in valor.cuentas],
            cuentas_con_pendientes=[
                CuentaPorLotearRespuesta.desde_valor(c) for c in valor.con_pendientes
            ],
        )
