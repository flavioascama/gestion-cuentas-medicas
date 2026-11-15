"""Cableado de FastAPI para /plataformas (Seccion 8.4, Fase 18). No
construye `IniciarSesionPlataforma`: ese caso de uso lo ejecuta el
trabajador (la unica implementacion de `AsistenteSesionPlataforma` es
Playwright, en `sistema/automatizacion/`, AD-02) -- la API solo solicita,
responde el CAPTCHA y consulta el estado."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.dominio.plataformas.casos_uso import (
    ListarSesionesPlataforma,
    ObtenerSesionPlataforma,
    ResponderCaptcha,
    SolicitarSesionPlataforma,
)
from app.dominio.plataformas.puertos import RepositorioSesionPlataforma
from app.dominio.puertos_comunes import Reloj, RepositorioTrabajos
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)


def obtener_repositorio_sesion_plataforma(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioSesionPlataforma:
    return RepositorioSesionPlataformaSql(sesion)


def obtener_repositorio_trabajos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrabajos:
    return RepositorioTrabajosSql(sesion)


def construir_solicitar_sesion_plataforma(
    repositorio: RepositorioSesionPlataforma = Depends(obtener_repositorio_sesion_plataforma),
    repositorio_trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarSesionPlataforma:
    return SolicitarSesionPlataforma(repositorio, repositorio_trabajos, reloj)


def construir_responder_captcha(
    repositorio: RepositorioSesionPlataforma = Depends(obtener_repositorio_sesion_plataforma),
) -> ResponderCaptcha:
    return ResponderCaptcha(repositorio)


def construir_listar_sesiones_plataforma(
    repositorio: RepositorioSesionPlataforma = Depends(obtener_repositorio_sesion_plataforma),
) -> ListarSesionesPlataforma:
    return ListarSesionesPlataforma(repositorio)


def construir_obtener_sesion_plataforma(
    repositorio: RepositorioSesionPlataforma = Depends(obtener_repositorio_sesion_plataforma),
) -> ObtenerSesionPlataforma:
    return ObtenerSesionPlataforma(repositorio)
