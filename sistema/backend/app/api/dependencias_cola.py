"""Cableado de FastAPI para /trabajos (Fase 18)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.cola.casos_uso import ObtenerTrabajo
from app.dominio.puertos_comunes import RepositorioTrabajos
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion


def obtener_repositorio_trabajos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrabajos:
    return RepositorioTrabajosSql(sesion)


def construir_obtener_trabajo(
    repositorio: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
) -> ObtenerTrabajo:
    return ObtenerTrabajo(repositorio)
