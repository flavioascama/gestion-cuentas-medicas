"""Esquemas Pydantic de /cuentas (Fase 18)."""

from __future__ import annotations

import re
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.acreditacion.puertos import AcreditacionRegistrada
from app.dominio.integracion.puertos_consulta import (
    DetalleCuenta,
    ResumenCie10,
    ResumenCuenta,
    ResumenIafas,
)
from app.dominio.integracion.puertos_ingesta import (
    DatosNuevaCuenta,
    PiezaCompletitud,
    ResultadoCompletitud,
)
from app.dominio.pse.puertos import ResultadoEmisionComprobante


class ResumenIafasRespuesta(BaseModel):
    id: int
    codigo: str
    razon_social: str

    @staticmethod
    def desde_valor(valor: ResumenIafas) -> ResumenIafasRespuesta:
        return ResumenIafasRespuesta(**campos(valor))


class ResumenCie10Respuesta(BaseModel):
    codigo: str
    descripcion: str

    @staticmethod
    def desde_valor(valor: ResumenCie10) -> ResumenCie10Respuesta:
        return ResumenCie10Respuesta(**campos(valor))


class ResumenCuentaRespuesta(BaseModel):
    id: int
    identificacion_interna: str
    estado: str
    fecha_prestacion: date
    nombres_asegurado: str
    apellidos_asegurado: str
    iafas_codigo: str
    iafas_razon_social: str

    @staticmethod
    def desde_valor(valor: ResumenCuenta) -> ResumenCuentaRespuesta:
        return ResumenCuentaRespuesta(**campos(valor))


class ProcedimientoRespuesta(BaseModel):
    id: int
    codigo_asignado: str
    descripcion_registrada: str
    cantidad: int
    monto_unitario: Decimal
    fecha: date | None


class ProductoRespuesta(BaseModel):
    tipo_producto: str
    catalogo: str
    codigo_producto: str
    cantidad_venta: str
    id: int
    correlativo: int
    nombre: str | None
    fecha_dispensacion: date | None
    monto_presentado: str


class DetalleCuentaRespuesta(BaseModel):
    id: int
    identificacion_interna: str
    estado: str
    fecha_prestacion: date
    hora_prestacion: time
    numero_historia_clinica: str | None
    diagnostico_principal_cie10: str | None
    nombres_asegurado: str
    apellidos_asegurado: str
    tipo_documento_asegurado: str
    numero_documento_asegurado: str
    iafas_codigo: str
    iafas_razon_social: str
    ipress_codigo: str
    procedimientos: list[ProcedimientoRespuesta]
    productos: list[ProductoRespuesta]
    datos_clinicos_reservados: bool = False
    # Atencion importada del sistema hospitalario (2026-11-19). El medico y
    # los diagnosticos secundarios no se muestran a tesoreria.
    tipo_atencion: str = "AMBULATORIA"
    atencion_origen_id: str | None = None
    nombre_medico: str | None = None
    colegiatura_medico: str | None = None
    diagnosticos_secundarios_cie10: list[str] = []
    fecha_ingreso_hospitalario: date | None = None
    fecha_alta_hospitalaria: date | None = None
    # Descripcion del catalogo CIE-10 por codigo; vacia para tesoreria.
    descripciones_cie10: dict[str, str] = {}
    asegurado_corregible: bool = False

    @staticmethod
    def desde_valor(valor: DetalleCuenta) -> DetalleCuentaRespuesta:
        excluidos = (
            "procedimientos",
            "productos",
            "diagnosticos_secundarios_cie10",
            "descripciones_cie10",
        )
        datos = {k: v for k, v in campos(valor).items() if k not in excluidos}
        return DetalleCuentaRespuesta(
            **datos,
            procedimientos=[ProcedimientoRespuesta(**campos(p)) for p in valor.procedimientos],
            productos=[ProductoRespuesta(**campos(p)) for p in valor.productos],
            diagnosticos_secundarios_cie10=list(valor.diagnosticos_secundarios_cie10),
            descripciones_cie10=dict(valor.descripciones_cie10),
        )


class RespuestaTrabajoEncolado(BaseModel):
    trabajo_id: int


_DNI = "1"


def error_numero_documento(tipo: str, numero: str) -> str | None:
    """Tabla 2, campo 10 de la trama: el DNI lleva 8 digitos; los demas
    documentos, no en blanco (el largo maximo lo pone el esquema)."""
    if tipo == _DNI and not re.fullmatch(r"[0-9]{8}", numero):
        return "El DNI debe tener exactamente 8 dígitos."
    if not numero.strip():
        return "Ingrese el número de documento."
    return None


class SolicitudNuevaCuenta(BaseModel):
    tipo_documento_asegurado: str = Field(min_length=1, max_length=1)
    numero_documento_asegurado: str = Field(min_length=1, max_length=15)
    nombres_asegurado: str = Field(min_length=1, max_length=150)
    apellidos_asegurado: str = Field(min_length=1, max_length=150)
    iafas_id: int
    fecha_prestacion: date
    hora_prestacion: time
    diagnostico_principal_cie10: str | None = None

    def a_valor(self) -> DatosNuevaCuenta:
        return DatosNuevaCuenta(**self.model_dump())


class SolicitudBuscarAsegurado(BaseModel):
    # Va en el cuerpo y no en la direccion: el documento del asegurado no
    # debe quedar en los registros de acceso.
    tipo_documento: str = Field(min_length=1, max_length=1)
    numero_documento: str = Field(min_length=1, max_length=15)


class SolicitudCorregirAsegurado(BaseModel):
    # Solo nombres y apellidos: el documento no se corrige.
    nombres_asegurado: str = Field(min_length=1, max_length=150)
    apellidos_asegurado: str = Field(min_length=1, max_length=150)


class AseguradoRegistradoRespuesta(BaseModel):
    nombres: str
    apellidos: str
    iafas_id: int


class RespuestaCuentaCreada(BaseModel):
    cuenta_id: int


class RespuestaComprobantePago(BaseModel):
    documento_id: int
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date

    @staticmethod
    def desde_valor(valor: ResultadoEmisionComprobante) -> RespuestaComprobantePago:
        return RespuestaComprobantePago(
            documento_id=valor.documento_id,
            tipo_documento_pago=valor.comprobante.tipo_documento_pago,
            serie=valor.comprobante.serie,
            numero=valor.comprobante.numero,
            fecha_emision=valor.comprobante.fecha_emision,
        )


class PiezaCompletitudRespuesta(BaseModel):
    clave: str
    etiqueta: str
    completa: bool
    bloquea: bool
    accion: str | None

    @staticmethod
    def desde_valor(valor: PiezaCompletitud) -> PiezaCompletitudRespuesta:
        return PiezaCompletitudRespuesta(**campos(valor))


class LoteDeCuentaRespuesta(BaseModel):
    lote_id: int
    numero: str
    estado: str


class SolicitudDiagnostico(BaseModel):
    codigo_cie10: str = Field(min_length=3, max_length=6)


class RespuestaDiagnostico(BaseModel):
    codigo_cie10: str


class RespuestaCompletitudCuenta(BaseModel):
    cuenta_id: int
    estado_cuenta: str
    completa: bool
    piezas: list[PiezaCompletitudRespuesta]
    # El lote mas reciente en que entro la cuenta, si entro en alguno.
    lote: LoteDeCuentaRespuesta | None = None

    @staticmethod
    def desde_valor(valor: ResultadoCompletitud) -> RespuestaCompletitudCuenta:
        return RespuestaCompletitudCuenta(
            cuenta_id=valor.cuenta_id,
            estado_cuenta=valor.estado_cuenta,
            completa=valor.completa,
            piezas=[PiezaCompletitudRespuesta.desde_valor(p) for p in valor.piezas],
            lote=LoteDeCuentaRespuesta(**campos(valor.lote)) if valor.lote else None,
        )


class AcreditacionRespuesta(BaseModel):
    id: int
    instante: str
    componente_ejecutor: str
    condicion_cobertura: str
    codigo_autorizacion: str
    tipo_documento_autorizacion: str
    codigo_asegurado: str
    tipo_afiliacion: str
    plan: str | None
    vigente_desde: date | None
    vigente_hasta: date | None
    tipo_copago: str | None
    monto_copago_fijo: str | None
    porcentaje_coaseguro: int | None
    preexistencias: list[str]
    # La cuenta sigue REGISTRADA y sin comprobante: se puede volver a consultar.
    admite_reconsulta: bool = False
    # El robot capturo la Solicitud de Atencion Medica (no en contingencia).
    tiene_solicitud_atencion: bool = False

    @staticmethod
    def desde_valor(valor: AcreditacionRegistrada) -> AcreditacionRespuesta:
        r = valor.resultado
        return AcreditacionRespuesta(
            id=valor.id,
            instante=valor.instante.isoformat(),
            componente_ejecutor=valor.componente_ejecutor,
            condicion_cobertura=r.condicion_cobertura,
            codigo_autorizacion=r.codigo_autorizacion,
            tipo_documento_autorizacion=r.tipo_documento_autorizacion,
            codigo_asegurado=r.codigo_asegurado,
            tipo_afiliacion=r.tipo_afiliacion,
            plan=r.plan,
            vigente_desde=r.vigente_desde,
            vigente_hasta=r.vigente_hasta,
            tipo_copago=r.tipo_copago,
            monto_copago_fijo=str(r.monto_copago_fijo) if r.monto_copago_fijo is not None else None,
            porcentaje_coaseguro=r.porcentaje_coaseguro,
            preexistencias=r.preexistencias,
            admite_reconsulta=valor.admite_reconsulta,
            tiene_solicitud_atencion=bool(r.ruta_evidencia),
        )
