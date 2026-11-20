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
from app.dominio.comunicaciones.entrega_respuesta import SolicitarNuevaEntregaRespuesta
from app.dominio.puertos_comunes import Reloj, RepositorioTrabajos
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.consulta_entregas_sql import ConsultaEntregasSql
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)
from app.infraestructura.persistencia.repositorio_documentos_pago_sql import (
    RepositorioDocumentosPagoSql,
)
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioObservacionesSql,
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
    sesion: AsyncSession = Depends(obtener_sesion),
) -> EncolarRespuestaIafas:
    return EncolarRespuestaIafas(repositorio, trabajos, reloj, RepositorioDocumentosPagoSql(sesion))


def construir_solicitar_nueva_entrega(
    encolar: EncolarRespuestaIafas = Depends(construir_encolar_respuesta_iafas),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> SolicitarNuevaEntregaRespuesta:
    return SolicitarNuevaEntregaRespuesta(
        RepositorioObservacionesSql(sesion), ConsultaEntregasSql(sesion), encolar
    )
