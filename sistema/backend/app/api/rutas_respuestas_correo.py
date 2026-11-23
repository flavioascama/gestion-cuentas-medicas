"""Responder un correo de la IAFAS desde el sistema (2026-11-22): `POST` y
`GET /correos-iafas/{correo_id}/respuestas`. La respuesta sale del buzon de
la clinica (la envia el robot) y queda guardada con el correo."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.correos import (
    ConsultarCorreoIafas,
    ErrorCorreos,
    Solicitante,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_correos_sql import RepositorioCorreosSql
from app.infraestructura.persistencia.respuesta_correo_sql import (
    RespuestaCorreo,
    listar_respuestas,
    registrar_respuesta,
)

router = APIRouter(prefix="/correos-iafas", tags=["comunicaciones_iafas"])
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_RESPONDE = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)


class SolicitudRespuestaCorreo(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


class RespuestaCorreoRespuesta(BaseModel):
    id: int
    texto: str
    respondido_por: str
    respondido_en: datetime
    enviada_en: datetime | None

    @staticmethod
    def desde_valor(valor: RespuestaCorreo) -> RespuestaCorreoRespuesta:
        return RespuestaCorreoRespuesta(**campos(valor))


async def _exigir_correo(sesion: AsyncSession, correo_id: int, actor: CargaSesion) -> None:
    """El correo existe y quien pregunta lo puede ver."""
    consulta = ConsultarCorreoIafas(RepositorioCorreosSql(sesion), RegistroEventosSql(sesion))
    try:
        await consulta.ejecutar(
            correo_id, Solicitante(usuario_id=actor.usuario_id, nombre_usuario=actor.nombre_usuario)
        )
    except ErrorCorreos as error:
        raise ErrorAplicacion(
            "CORREO_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error


@router.get("/{correo_id}/respuestas", response_model=list[RespuestaCorreoRespuesta])
async def listar_respuestas_de_correo(
    correo_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_LECTURA),
) -> list[RespuestaCorreoRespuesta]:
    await _exigir_correo(sesion, correo_id, actor)
    respuestas = await listar_respuestas(sesion, correo_id)
    return [RespuestaCorreoRespuesta.desde_valor(r) for r in respuestas]


@router.post("/{correo_id}/respuestas", status_code=status.HTTP_204_NO_CONTENT)
async def responder_correo(
    correo_id: int,
    solicitud: SolicitudRespuestaCorreo,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_RESPONDE),
) -> None:
    await _exigir_correo(sesion, correo_id, actor)
    await registrar_respuesta(sesion, correo_id, solicitud.texto.strip(), actor.nombre_usuario)
