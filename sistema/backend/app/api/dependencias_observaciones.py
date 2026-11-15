"""Cableado de FastAPI para /observaciones (CU-08 a CU-10, Fase 26)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.dominio.observaciones.casos_uso import (
    AsignarResponsableObservacion,
    ListarCatalogoMotivos,
    ListarObservacionesPorCuenta,
    RegistrarObservacion,
    ResponderObservacion,
)
from app.dominio.observaciones.puertos import RepositorioCatalogoMotivos, RepositorioObservaciones
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Observabilidad, Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioCatalogoMotivosSql,
    RepositorioObservacionesSql,
)


def obtener_repositorio_observaciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioObservaciones:
    return RepositorioObservacionesSql(sesion)


def obtener_repositorio_catalogo_motivos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioCatalogoMotivos:
    return RepositorioCatalogoMotivosSql(sesion)


def obtener_repositorio_estado_cuenta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioEstadoCuenta:
    return RepositorioEstadoCuentaSql(sesion)


def obtener_observabilidad(sesion: AsyncSession = Depends(obtener_sesion)) -> Observabilidad:
    return Observabilidad(
        eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
    )


def construir_registrar_observacion(
    repositorio: RepositorioObservaciones = Depends(obtener_repositorio_observaciones),
    catalogo: RepositorioCatalogoMotivos = Depends(obtener_repositorio_catalogo_motivos),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarObservacion:
    return RegistrarObservacion(repositorio, catalogo, estado_cuenta, observabilidad, reloj)


def construir_asignar_responsable_observacion(
    repositorio: RepositorioObservaciones = Depends(obtener_repositorio_observaciones),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> AsignarResponsableObservacion:
    return AsignarResponsableObservacion(repositorio, observabilidad)


def construir_responder_observacion(
    repositorio: RepositorioObservaciones = Depends(obtener_repositorio_observaciones),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> ResponderObservacion:
    return ResponderObservacion(repositorio, estado_cuenta, observabilidad, reloj)


def construir_listar_observaciones_por_cuenta(
    repositorio: RepositorioObservaciones = Depends(obtener_repositorio_observaciones),
) -> ListarObservacionesPorCuenta:
    return ListarObservacionesPorCuenta(repositorio)


def construir_listar_catalogo_motivos(
    catalogo: RepositorioCatalogoMotivos = Depends(obtener_repositorio_catalogo_motivos),
) -> ListarCatalogoMotivos:
    return ListarCatalogoMotivos(catalogo)
