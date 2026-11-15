"""Cableado de FastAPI para /cuentas/{id}/rechazo y
/cuentas/{id}/correccion-reenvio (T-05)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias_cierre import obtener_observabilidad, obtener_repositorio_estado_cuenta
from app.dominio.orquestacion.casos_uso import CorregirCuentaRechazada, ObtenerRechazoCuenta
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta, RepositorioRechazoCuenta
from app.dominio.puertos_comunes import Observabilidad
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_rechazo_cuenta_sql import (
    RepositorioRechazoCuentaSql,
)


def obtener_repositorio_rechazo_cuenta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioRechazoCuenta:
    return RepositorioRechazoCuentaSql(sesion)


def construir_obtener_rechazo_cuenta(
    repositorio: RepositorioRechazoCuenta = Depends(obtener_repositorio_rechazo_cuenta),
) -> ObtenerRechazoCuenta:
    return ObtenerRechazoCuenta(repositorio)


def construir_corregir_cuenta_rechazada(
    estado_cuenta: RepositorioEstadoCuenta = Depends(obtener_repositorio_estado_cuenta),
    rechazos: RepositorioRechazoCuenta = Depends(obtener_repositorio_rechazo_cuenta),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> CorregirCuentaRechazada:
    return CorregirCuentaRechazada(estado_cuenta, rechazos, observabilidad)
