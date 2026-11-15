"""Cableado de FastAPI para /comunicaciones-iafas (2026-11-13)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.dominio.comunicaciones.casos_uso import (
    EncolarRespuestaIafas,
    ListarComunicacionesIafas,
    RepositorioComunicaciones,
    SolicitarRevisionComunicaciones,
)
from app.dominio.puertos_comunes import Reloj, RepositorioTrabajos
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)


def obtener_repositorio_comunicaciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioComunicaciones:
    return RepositorioComunicacionesSql(sesion)


def obtener_repositorio_trabajos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrabajos:
    return RepositorioTrabajosSql(sesion)


def construir_listar_comunicaciones(
    repositorio: RepositorioComunicaciones = Depends(obtener_repositorio_comunicaciones),
) -> ListarComunicacionesIafas:
    return ListarComunicacionesIafas(repositorio)


def construir_solicitar_revision(
    repositorio: RepositorioComunicaciones = Depends(obtener_repositorio_comunicaciones),
    trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarRevisionComunicaciones:
    return SolicitarRevisionComunicaciones(repositorio, trabajos, reloj)


def construir_encolar_respuesta_iafas(
    repositorio: RepositorioComunicaciones = Depends(obtener_repositorio_comunicaciones),
    trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> EncolarRespuestaIafas:
    return EncolarRespuestaIafas(repositorio, trabajos, reloj)
