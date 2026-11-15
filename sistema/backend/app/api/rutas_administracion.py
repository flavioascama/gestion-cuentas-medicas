"""Seccion 12, pantalla 8: catalogo GTIN para el administrador (Fase 19;
carga de versiones y productos por version desde el 2026-11-13, CU-18).
`GET`/`POST /catalogo-cpms/versiones` viven en `rutas_cpms.py` (Fase 18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.dependencias_administracion import construir_listar_versiones_catalogo_gtin
from app.api.esquemas_administracion import VersionCatalogoGtinRespuesta
from app.api.rutas_farmacia import ProductoCatalogoRespuesta
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.farmacia.casos_uso import (
    CargarCatalogoGtin,
    ListarProductosCatalogoGtin,
    ListarVersionesCatalogoGtin,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.cargador_catalogo_gtin import (
    CargadorCatalogoGtinSql,
    ErrorCatalogoGtinSinTrazabilidad,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_catalogo_gtin_sql import (
    RepositorioCatalogoGtinSql,
)

router = APIRouter(tags=["administracion"])
_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)


@router.get("/catalogo-gtin/versiones", response_model=list[VersionCatalogoGtinRespuesta])
async def listar_versiones_catalogo_gtin(
    caso_uso: ListarVersionesCatalogoGtin = Depends(construir_listar_versiones_catalogo_gtin),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[VersionCatalogoGtinRespuesta]:
    versiones = await caso_uso.ejecutar()
    return [VersionCatalogoGtinRespuesta.desde_valor(v) for v in versiones]


@router.post(
    "/catalogo-gtin/versiones",
    response_model=VersionCatalogoGtinRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def cargar_catalogo_gtin(
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> VersionCatalogoGtinRespuesta:
    caso_uso = CargarCatalogoGtin(CargadorCatalogoGtinSql(sesion), RegistroEventosSql(sesion))
    try:
        version = await caso_uso.ejecutar(actor.nombre_usuario, actor.usuario_id)
    except ErrorCatalogoGtinSinTrazabilidad as error:
        raise ErrorAplicacion(
            "CATALOGO_GTIN_SIN_TRAZABILIDAD", str(error), estado_http=409
        ) from error
    return VersionCatalogoGtinRespuesta.desde_valor(version)


@router.get(
    "/catalogo-gtin/versiones/{version_id}/productos",
    response_model=list[ProductoCatalogoRespuesta],
)
async def listar_productos_catalogo_gtin(
    version_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[ProductoCatalogoRespuesta]:
    productos = await ListarProductosCatalogoGtin(RepositorioCatalogoGtinSql(sesion)).ejecutar(
        version_id
    )
    return [ProductoCatalogoRespuesta.desde_valor(p) for p in productos]
