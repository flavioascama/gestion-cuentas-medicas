"""Bandeja de avisos (CU-08, CU-09, CU-11, CU-14): cualquier usuario
autenticado ve los avisos destinados a sus roles; un rol sin avisos en el
catalogo recibe una lista vacia, no un 403."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_usuario_actual
from app.api.dependencias_avisos import construir_listar_avisos, construir_marcar_aviso_atendido
from app.api.esquemas_avisos import AvisoRespuesta
from app.api.nombres_actores import con_nombres_en_avisos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.avisos.casos_uso import (
    ErrorAvisoNoEncontrado,
    ErrorAvisoNoMarcable,
    ListarAvisos,
    MarcarAvisoAtendido,
)
from app.infraestructura.persistencia.base import obtener_sesion

router = APIRouter(prefix="/avisos", tags=["avisos"])


@router.get("", response_model=list[AvisoRespuesta])
async def listar_avisos(
    limite: int = Query(default=100, ge=1, le=500),
    caso_uso: ListarAvisos = Depends(construir_listar_avisos),
    actor: CargaSesion = Depends(obtener_usuario_actual),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> list[AvisoRespuesta]:
    avisos = await caso_uso.ejecutar(actor.roles, limite, actor.usuario_id, actor.nombre_usuario)
    return [AvisoRespuesta.desde_valor(a) for a in await con_nombres_en_avisos(sesion, avisos)]


@router.post("/{evento_id}/atendido", status_code=status.HTTP_204_NO_CONTENT)
async def marcar_aviso_atendido(
    evento_id: str,
    caso_uso: MarcarAvisoAtendido = Depends(construir_marcar_aviso_atendido),
    actor: CargaSesion = Depends(obtener_usuario_actual),
) -> None:
    """Solo quien recibe el aviso, y solo los que no se resuelven solos."""
    try:
        await caso_uso.ejecutar(evento_id, actor)
    except ErrorAvisoNoEncontrado as error:
        raise ErrorAplicacion(
            "AVISO_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorAvisoNoMarcable as error:
        raise ErrorAplicacion(
            "AVISO_NO_MARCABLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
