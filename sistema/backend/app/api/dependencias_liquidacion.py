"""Cableado de FastAPI para /cuentas/{id}/liquidacion y /cuentas/{id}/
pago (CU-12, Fase 28)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.dominio.liquidacion.casos_uso import (
    ConciliarPago,
    ObtenerLiquidacion,
    RegistrarLiquidacion,
)
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
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
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioObservacionesSql,
)


def obtener_repositorio_liquidaciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioLiquidaciones:
    return RepositorioLiquidacionesSql(sesion)


def obtener_repositorio_estado_cuenta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioEstadoCuenta:
    return RepositorioEstadoCuentaSql(sesion)


def obtener_observabilidad(sesion: AsyncSession = Depends(obtener_sesion)) -> Observabilidad:
    return Observabilidad(
        eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
    )


def construir_registrar_liquidacion(
    repositorio: RepositorioLiquidaciones = Depends(obtener_repositorio_liquidaciones),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RegistrarLiquidacion:
    return RegistrarLiquidacion(
        repositorio, estado_cuenta, observabilidad, reloj, RepositorioObservacionesSql(sesion)
    )


def construir_conciliar_pago(
    repositorio: RepositorioLiquidaciones = Depends(obtener_repositorio_liquidaciones),
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> ConciliarPago:
    return ConciliarPago(repositorio, estado_cuenta, observabilidad, reloj)


def construir_obtener_liquidacion(
    repositorio: RepositorioLiquidaciones = Depends(obtener_repositorio_liquidaciones),
) -> ObtenerLiquidacion:
    return ObtenerLiquidacion(repositorio)
