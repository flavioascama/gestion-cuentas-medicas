"""Cableado de FastAPI para /avisos."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.avisos.casos_uso import ListarAvisos, MarcarAvisoAtendido
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_avisos_sql import RepositorioAvisosSql


def construir_listar_avisos(sesion: AsyncSession = Depends(obtener_sesion)) -> ListarAvisos:
    return ListarAvisos(RepositorioAvisosSql(sesion))


def construir_marcar_aviso_atendido(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> MarcarAvisoAtendido:
    return MarcarAvisoAtendido(RepositorioAvisosSql(sesion), RegistroEventosSql(sesion))
