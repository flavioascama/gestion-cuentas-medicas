"""Cableado de FastAPI para /catalogo-gtin (Fase 19, Seccion 12, pantalla
de administracion)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.farmacia.casos_uso import ListarVersionesCatalogoGtin
from app.dominio.farmacia.puertos import RepositorioCatalogoGtin
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_catalogo_gtin_sql import (
    RepositorioCatalogoGtinSql,
)


def obtener_repositorio_catalogo_gtin(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioCatalogoGtin:
    return RepositorioCatalogoGtinSql(sesion)


def construir_listar_versiones_catalogo_gtin(
    repositorio: RepositorioCatalogoGtin = Depends(obtener_repositorio_catalogo_gtin),
) -> ListarVersionesCatalogoGtin:
    return ListarVersionesCatalogoGtin(repositorio)
