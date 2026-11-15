"""Bandeja de avisos (CU-08, CU-09, CU-11, CU-14): cualquier usuario
autenticado ve los avisos destinados a sus roles; un rol sin avisos en el
catalogo recibe una lista vacia, no un 403."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencias import obtener_usuario_actual
from app.api.dependencias_avisos import construir_listar_avisos
from app.api.esquemas_avisos import AvisoRespuesta
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.avisos.casos_uso import ListarAvisos

router = APIRouter(prefix="/avisos", tags=["avisos"])


@router.get("", response_model=list[AvisoRespuesta])
async def listar_avisos(
    limite: int = Query(default=100, ge=1, le=500),
    caso_uso: ListarAvisos = Depends(construir_listar_avisos),
    actor: CargaSesion = Depends(obtener_usuario_actual),
) -> list[AvisoRespuesta]:
    avisos = await caso_uso.ejecutar(actor.roles, limite)
    return [AvisoRespuesta.desde_valor(a) for a in avisos]
