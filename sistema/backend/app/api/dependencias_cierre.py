"""Cableado de FastAPI para /cuentas/{id}/cierre, /cuentas/{id}/
anulacion y /anulaciones (CU-13, RF-21, Fase 28)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.api.dependencias_observaciones import obtener_repositorio_observaciones
from app.dominio.cierre.casos_uso import (
    CerrarCuenta,
    ListarSolicitudesAnulacionPendientes,
    ResolverSolicitudAnulacion,
    SolicitarAnulacion,
)
from app.dominio.cierre.puertos import RepositorioSolicitudesAnulacion
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.observaciones.puertos import RepositorioObservaciones
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Observabilidad, Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_liquidaciones_sql import (
    RepositorioLiquidacionesSql,
)
from app.infraestructura.persistencia.repositorio_solicitudes_anulacion_sql import (
    RepositorioSolicitudesAnulacionSql,
)


def obtener_repositorio_liquidaciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioLiquidaciones:
    return RepositorioLiquidacionesSql(sesion)


def obtener_repositorio_solicitudes_anulacion(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioSolicitudesAnulacion:
    return RepositorioSolicitudesAnulacionSql(sesion)


def obtener_repositorio_estado_cuenta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioEstadoCuenta:
    return RepositorioEstadoCuentaSql(sesion)


def obtener_observabilidad(sesion: AsyncSession = Depends(obtener_sesion)) -> Observabilidad:
    return Observabilidad(
        eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
    )


def construir_cerrar_cuenta(
    liquidaciones: RepositorioLiquidaciones = Depends(obtener_repositorio_liquidaciones),
    observaciones: RepositorioObservaciones = Depends(obtener_repositorio_observaciones),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> CerrarCuenta:
    return CerrarCuenta(liquidaciones, observaciones, estado_cuenta, observabilidad)


def construir_solicitar_anulacion(
    repositorio: RepositorioSolicitudesAnulacion = Depends(
        obtener_repositorio_solicitudes_anulacion
    ),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarAnulacion:
    return SolicitarAnulacion(repositorio, estado_cuenta, observabilidad, reloj)


def construir_resolver_solicitud_anulacion(
    repositorio: RepositorioSolicitudesAnulacion = Depends(
        obtener_repositorio_solicitudes_anulacion
    ),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> ResolverSolicitudAnulacion:
    return ResolverSolicitudAnulacion(repositorio, estado_cuenta, observabilidad, reloj)


def construir_listar_solicitudes_anulacion_pendientes(
    repositorio: RepositorioSolicitudesAnulacion = Depends(
        obtener_repositorio_solicitudes_anulacion
    ),
) -> ListarSolicitudesAnulacionPendientes:
    return ListarSolicitudesAnulacionPendientes(repositorio)
