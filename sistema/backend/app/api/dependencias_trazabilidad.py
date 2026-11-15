"""Cableado de FastAPI para /cuentas/{id}/historial, /indicadores y
/cuentas/{id}/expediente (CU-14 a CU-16, Fase 29)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.dominio.puertos_comunes import Observabilidad, Reloj
from app.dominio.trazabilidad.casos_uso import (
    ConsultarHistorialCuenta,
    ConsultarHistorialLote,
    ExportarExpediente,
    VisualizarIndicadoresCiclo,
)
from app.dominio.trazabilidad.puertos import RepositorioTrazabilidad
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_trazabilidad_sql import (
    RepositorioTrazabilidadSql,
)


def obtener_repositorio_trazabilidad(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrazabilidad:
    return RepositorioTrazabilidadSql(sesion)


def obtener_observabilidad(sesion: AsyncSession = Depends(obtener_sesion)) -> Observabilidad:
    return Observabilidad(
        eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
    )


def construir_consultar_historial_cuenta(
    repositorio: RepositorioTrazabilidad = Depends(obtener_repositorio_trazabilidad),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> ConsultarHistorialCuenta:
    return ConsultarHistorialCuenta(repositorio, observabilidad)


def construir_consultar_historial_lote(
    repositorio: RepositorioTrazabilidad = Depends(obtener_repositorio_trazabilidad),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> ConsultarHistorialLote:
    return ConsultarHistorialLote(repositorio, observabilidad)


def construir_visualizar_indicadores_ciclo(
    repositorio: RepositorioTrazabilidad = Depends(obtener_repositorio_trazabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> VisualizarIndicadoresCiclo:
    return VisualizarIndicadoresCiclo(repositorio, reloj)


def construir_exportar_expediente(
    repositorio: RepositorioTrazabilidad = Depends(obtener_repositorio_trazabilidad),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> ExportarExpediente:
    return ExportarExpediente(repositorio, observabilidad, reloj)
