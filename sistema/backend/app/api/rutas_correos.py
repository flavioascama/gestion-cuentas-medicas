"""/correos-iafas (2026-11-15): los correos que llegaron al buzon de cuentas
medicas, tambien los que el robot no pudo aplicar solo. La bandeja entrega
el remitente, el asunto y el estado; el texto y los adjuntos solo se
entregan en el detalle, y cada consulta y descarga queda en la bitacora
(C-08). Vincular o descartar un correo por revisar es del analista y del
jefe de cuentas medicas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.correos import (
    AdjuntoRegistrado,
    ConsultarCorreoIafas,
    CorreoRegistrado,
    DescargarAdjuntoCorreo,
    DescartarCorreoIafas,
    ErrorCorreoInexistente,
    ErrorCorreos,
    ErrorCorreoYaResuelto,
    ErrorCuentaDesconocida,
    ErrorMotivoRequerido,
    ListarCorreosIafas,
    Solicitante,
    VincularCorreoIafas,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_correos_sql import RepositorioCorreosSql

router = APIRouter(prefix="/correos-iafas", tags=["comunicaciones_iafas"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_REVISA = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)

EstadoFiltro = Literal["PROCESADO", "POR_REVISAR", "VINCULADO", "DESCARTADO"]


class AdjuntoCorreoRespuesta(BaseModel):
    id: int
    nombre: str
    tipo: str
    tamano: int
    huella: str
    almacenado: bool
    motivo_omision: str | None

    @staticmethod
    def desde_valor(valor: AdjuntoRegistrado) -> AdjuntoCorreoRespuesta:
        return AdjuntoCorreoRespuesta(**campos(valor))


class CorreoIafasRespuesta(BaseModel):
    id: int
    remitente: str
    codigo_iafas: str | None
    asunto: str
    fecha: datetime | None
    recibido_en: datetime
    estado: str
    motivo_revision: str | None
    comunicacion_codigo: str | None
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    huella: str
    resuelto_por: str | None
    resuelto_en: datetime | None
    nota_resolucion: str | None
    cantidad_adjuntos: int

    @staticmethod
    def desde_valor(valor: CorreoRegistrado) -> CorreoIafasRespuesta:
        datos = campos(valor)
        return CorreoIafasRespuesta(**{c: datos[c] for c in CorreoIafasRespuesta.model_fields})


class CorreoIafasDetalleRespuesta(CorreoIafasRespuesta):
    texto: str
    adjuntos: list[AdjuntoCorreoRespuesta]

    @staticmethod
    def desde_valor(valor: CorreoRegistrado) -> CorreoIafasDetalleRespuesta:
        resumen = CorreoIafasRespuesta.desde_valor(valor).model_dump()
        return CorreoIafasDetalleRespuesta(
            **resumen,
            texto=valor.texto or "",
            adjuntos=[AdjuntoCorreoRespuesta.desde_valor(a) for a in valor.adjuntos],
        )


class SolicitudVinculacion(BaseModel):
    identificacion_interna: str = Field(min_length=1, max_length=10)


class SolicitudDescarte(BaseModel):
    motivo: str = Field(min_length=1, max_length=300)


def _solicitante(actor: CargaSesion) -> Solicitante:
    return Solicitante(usuario_id=actor.usuario_id, nombre_usuario=actor.nombre_usuario)


def _error_http(error: ErrorCorreos) -> ErrorAplicacion:
    if isinstance(error, ErrorCorreoInexistente):
        return ErrorAplicacion("CORREO_NO_ENCONTRADO", str(error), estado_http=404)
    if isinstance(error, ErrorCuentaDesconocida):
        return ErrorAplicacion("CUENTA_NO_ENCONTRADA", str(error), estado_http=404)
    if isinstance(error, ErrorCorreoYaResuelto):
        return ErrorAplicacion("CORREO_YA_REVISADO", str(error), estado_http=409)
    if isinstance(error, ErrorMotivoRequerido):
        return ErrorAplicacion("MOTIVO_REQUERIDO", str(error), estado_http=422)
    return ErrorAplicacion("CORREO_NO_DISPONIBLE", str(error), estado_http=409)


@router.get("", response_model=list[CorreoIafasRespuesta])
async def listar_correos(
    estado: EstadoFiltro | None = None,
    cuenta_id: int | None = None,
    sesion: AsyncSession = Depends(obtener_sesion),
    _: CargaSesion = Depends(_LECTURA),
) -> list[CorreoIafasRespuesta]:
    correos = await ListarCorreosIafas(RepositorioCorreosSql(sesion)).ejecutar(estado, cuenta_id)
    return [CorreoIafasRespuesta.desde_valor(correo) for correo in correos]


@router.get("/{correo_id}", response_model=CorreoIafasDetalleRespuesta)
async def consultar_correo(
    correo_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_LECTURA),
) -> CorreoIafasDetalleRespuesta:
    caso_uso = ConsultarCorreoIafas(RepositorioCorreosSql(sesion), RegistroEventosSql(sesion))
    try:
        correo = await caso_uso.ejecutar(correo_id, _solicitante(actor))
    except ErrorCorreos as error:
        raise _error_http(error) from error
    return CorreoIafasDetalleRespuesta.desde_valor(correo)


@router.get("/{correo_id}/adjuntos/{adjunto_id}")
async def descargar_adjunto(
    correo_id: int,
    adjunto_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_LECTURA),
) -> Response:
    caso_uso = DescargarAdjuntoCorreo(RepositorioCorreosSql(sesion), RegistroEventosSql(sesion))
    try:
        adjunto = await caso_uso.ejecutar(correo_id, adjunto_id, _solicitante(actor))
    except ErrorCorreos as error:
        raise _error_http(error) from error
    # Siempre como descarga y sin que el navegador adivine el tipo: un
    # adjunto nunca se abre dentro de la aplicacion.
    return Response(
        content=adjunto.contenido,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(adjunto.nombre)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post("/{correo_id}/vinculacion", response_model=CorreoIafasDetalleRespuesta)
async def vincular_correo(
    correo_id: int,
    solicitud: SolicitudVinculacion,
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
    actor: CargaSesion = Depends(_REVISA),
) -> CorreoIafasDetalleRespuesta:
    caso_uso = VincularCorreoIafas(RepositorioCorreosSql(sesion), RegistroEventosSql(sesion), reloj)
    try:
        correo = await caso_uso.ejecutar(
            correo_id, solicitud.identificacion_interna, _solicitante(actor)
        )
    except ErrorCorreos as error:
        raise _error_http(error) from error
    return CorreoIafasDetalleRespuesta.desde_valor(correo)


@router.post("/{correo_id}/descarte", response_model=CorreoIafasDetalleRespuesta)
async def descartar_correo(
    correo_id: int,
    solicitud: SolicitudDescarte,
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
    actor: CargaSesion = Depends(_REVISA),
) -> CorreoIafasDetalleRespuesta:
    caso_uso = DescartarCorreoIafas(
        RepositorioCorreosSql(sesion), RegistroEventosSql(sesion), reloj
    )
    try:
        correo = await caso_uso.ejecutar(correo_id, solicitud.motivo, _solicitante(actor))
    except ErrorCorreos as error:
        raise _error_http(error) from error
    return CorreoIafasDetalleRespuesta.desde_valor(correo)
