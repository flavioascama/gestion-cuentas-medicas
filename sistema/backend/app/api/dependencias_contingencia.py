"""Cableado de FastAPI del modo de contingencia (RF-23, C-18)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.api.dependencias_cierre import obtener_observabilidad
from app.api.dependencias_cuentas import obtener_repositorio_acreditacion
from app.api.dependencias_lotes import obtener_repositorio_validacion_oficial
from app.compartido.rutas import raiz_artefactos_s01
from app.dominio.acreditacion.puertos import RepositorioAcreditacion
from app.dominio.contingencia.casos_uso import (
    ConsultarDisponibilidadContingencia,
    ConsultarUltimaConsultaCobertura,
    ListarRegistrosContingencia,
    RegistrarCoberturaContingencia,
    RevisarRegistroContingencia,
)
from app.dominio.contingencia.puertos import RepositorioContingencia
from app.dominio.integracion.puertos_validacion import RepositorioValidacionOficial
from app.dominio.puertos_comunes import Observabilidad, Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_contingencia_sql import (
    RepositorioContingenciaSql,
)
from app.infraestructura.tedef.registrar_validacion_contingencia import (
    RegistrarValidacionContingencia,
    RepositoriosValidacionContingencia,
)


def obtener_repositorio_contingencia(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioContingencia:
    return RepositorioContingenciaSql(sesion)


def construir_disponibilidad_contingencia(
    repositorio: RepositorioContingencia = Depends(obtener_repositorio_contingencia),
    acreditaciones: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
) -> ConsultarDisponibilidadContingencia:
    return ConsultarDisponibilidadContingencia(repositorio, acreditaciones)


def construir_ultima_consulta_cobertura(
    repositorio: RepositorioContingencia = Depends(obtener_repositorio_contingencia),
    acreditaciones: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
) -> ConsultarUltimaConsultaCobertura:
    return ConsultarUltimaConsultaCobertura(repositorio, acreditaciones)


def construir_registrar_cobertura_contingencia(
    disponibilidad: ConsultarDisponibilidadContingencia = Depends(
        construir_disponibilidad_contingencia
    ),
    acreditaciones: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarCoberturaContingencia:
    return RegistrarCoberturaContingencia(disponibilidad, acreditaciones, observabilidad, reloj)


def construir_registrar_validacion_contingencia(
    disponibilidad: ConsultarDisponibilidadContingencia = Depends(
        construir_disponibilidad_contingencia
    ),
    repositorio: RepositorioContingencia = Depends(obtener_repositorio_contingencia),
    validacion: RepositorioValidacionOficial = Depends(obtener_repositorio_validacion_oficial),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarValidacionContingencia:
    return RegistrarValidacionContingencia(
        disponibilidad,
        RepositoriosValidacionContingencia(contingencia=repositorio, validacion=validacion),
        observabilidad,
        reloj,
        raiz_artefactos_s01(),
    )


def construir_listar_registros_contingencia(
    repositorio: RepositorioContingencia = Depends(obtener_repositorio_contingencia),
) -> ListarRegistrosContingencia:
    return ListarRegistrosContingencia(repositorio)


def construir_revisar_registro_contingencia(
    repositorio: RepositorioContingencia = Depends(obtener_repositorio_contingencia),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
) -> RevisarRegistroContingencia:
    return RevisarRegistroContingencia(repositorio, observabilidad)
