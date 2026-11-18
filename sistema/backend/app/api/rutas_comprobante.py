"""CU-10 y RI-11: el comprobante vigente de la cuenta con su nota y sus
reemplazos; el reemplazo al refacturar y el registro de la nota de credito
o debito. Los registra el analista; los consultan los roles que consultan
la cuenta (Tabla 46)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.dependencias_cuentas import obtener_emisor_pse
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.pse.documentos import (
    ConsultarDocumentosPago,
    DatosNota,
    DocumentosPagoCuenta,
    EmisionPse,
    ErrorComprobanteConNota,
    ErrorCuentaInexistenteDocumento,
    ErrorDocumentoPago,
    ErrorEstadoNoAdmiteDocumento,
    ErrorNotaInvalida,
    ErrorNotaYaRegistrada,
    ErrorSinComprobante,
    ReemplazarComprobantePago,
    RegistrarNotaDocumento,
)
from app.dominio.pse.puertos import EmisorPse
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_comprobante_pago_sql import (
    RepositorioComprobantePagoSql,
)
from app.infraestructura.persistencia.repositorio_documentos_pago_sql import (
    RepositorioDocumentosPagoSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

router = APIRouter(prefix="/cuentas/{cuenta_id}/comprobante", tags=["cuentas"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)


class ComprobanteVigenteRespuesta(BaseModel):
    documento_id: int
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date
    valor_venta: Decimal | None = None
    igv: Decimal | None = None
    total: Decimal | None = None


class NotaDocumentoRespuesta(BaseModel):
    tipo: str
    serie: str
    numero: str
    monto: Decimal
    fecha: date
    motivo: str
    registrado_en: datetime
    registrado_por: str


class ComprobanteReemplazadoRespuesta(BaseModel):
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date
    reemplazado_en: datetime
    reemplazado_por: str
    motivo: str


class DocumentosPagoRespuesta(BaseModel):
    vigente: ComprobanteVigenteRespuesta
    nota: NotaDocumentoRespuesta | None
    reemplazados: list[ComprobanteReemplazadoRespuesta]

    @staticmethod
    def desde_valor(valor: DocumentosPagoCuenta) -> DocumentosPagoRespuesta:
        return DocumentosPagoRespuesta(
            vigente=ComprobanteVigenteRespuesta(**campos(valor.vigente)),
            nota=NotaDocumentoRespuesta(**campos(valor.nota)) if valor.nota else None,
            reemplazados=[ComprobanteReemplazadoRespuesta(**campos(r)) for r in valor.reemplazados],
        )


class SolicitudReemplazo(BaseModel):
    motivo: str = Field(min_length=1, max_length=300)


class SolicitudNota(BaseModel):
    """La serie, el numero y la fecha los da el PSE al emitir la nota."""

    tipo: str = Field(min_length=1, max_length=1)
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    motivo: str = Field(min_length=1, max_length=1)


def _error_http(error: ErrorDocumentoPago) -> ErrorAplicacion:
    if isinstance(error, ErrorCuentaInexistenteDocumento):
        return ErrorAplicacion("CUENTA_NO_ENCONTRADA", str(error), estado_http=404)
    if isinstance(error, ErrorSinComprobante):
        return ErrorAplicacion("SIN_COMPROBANTE", str(error), estado_http=409)
    if isinstance(error, ErrorEstadoNoAdmiteDocumento | ErrorNotaYaRegistrada):
        return ErrorAplicacion("ESTADO_NO_ADMITE_DOCUMENTO", str(error), estado_http=409)
    if isinstance(error, ErrorComprobanteConNota):
        return ErrorAplicacion("COMPROBANTE_CON_NOTA", str(error), estado_http=409)
    assert isinstance(error, ErrorNotaInvalida)
    return ErrorAplicacion("DATOS_INVALIDOS", str(error), estado_http=400)


@router.get("", response_model=DocumentosPagoRespuesta | None)
async def consultar_documentos_pago(
    cuenta_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> DocumentosPagoRespuesta | None:
    documentos = await ConsultarDocumentosPago(RepositorioDocumentosPagoSql(sesion)).ejecutar(
        cuenta_id
    )
    return DocumentosPagoRespuesta.desde_valor(documentos) if documentos else None


def construir_reemplazar(
    sesion: AsyncSession = Depends(obtener_sesion),
    emisor: EmisorPse = Depends(obtener_emisor_pse),
    reloj: Reloj = Depends(obtener_reloj),
) -> ReemplazarComprobantePago:
    return ReemplazarComprobantePago(
        RepositorioDocumentosPagoSql(sesion),
        EmisionPse(RepositorioComprobantePagoSql(sesion), emisor),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
        reloj,
    )


@router.post("/reemplazo", response_model=ComprobanteVigenteRespuesta, status_code=201)
async def reemplazar_comprobante(
    cuenta_id: int,
    solicitud: SolicitudReemplazo,
    caso_uso: ReemplazarComprobantePago = Depends(construir_reemplazar),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> ComprobanteVigenteRespuesta:
    try:
        vigente = await caso_uso.ejecutar(cuenta_id, solicitud.motivo, actor.nombre_usuario)
    except ErrorDocumentoPago as error:
        raise _error_http(error) from error
    return ComprobanteVigenteRespuesta(**campos(vigente))


def construir_registrar_nota(
    sesion: AsyncSession = Depends(obtener_sesion),
    emisor: EmisorPse = Depends(obtener_emisor_pse),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarNotaDocumento:
    return RegistrarNotaDocumento(
        RepositorioDocumentosPagoSql(sesion),
        EmisionPse(RepositorioComprobantePagoSql(sesion), emisor),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
        reloj,
    )


@router.post("/nota", response_model=NotaDocumentoRespuesta, status_code=status.HTTP_201_CREATED)
async def registrar_nota(
    cuenta_id: int,
    solicitud: SolicitudNota,
    caso_uso: RegistrarNotaDocumento = Depends(construir_registrar_nota),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> NotaDocumentoRespuesta:
    datos = DatosNota(**solicitud.model_dump())
    try:
        nota = await caso_uso.ejecutar(cuenta_id, datos, actor.nombre_usuario)
    except ErrorDocumentoPago as error:
        raise _error_http(error) from error
    return NotaDocumentoRespuesta(**campos(nota))
