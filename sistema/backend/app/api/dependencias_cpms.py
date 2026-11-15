"""Cableado de FastAPI para /cpms, /cuentas/{id}/procedimientos y
/catalogo-cpms (Seccion 8.2, Fase 18)."""

from __future__ import annotations

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.compartido.errores import ErrorAplicacion
from app.compartido.rutas import RAIZ_BACKEND
from app.dominio.cpms.casos_uso import ConfirmarCodigoCpms, ListarVersionesCpms, SugerirCodigoCpms
from app.dominio.cpms.puertos import MotorSugerenciaCpms, RepositorioCpms
from app.dominio.puertos_comunes import RegistroMediciones, Reloj
from app.infraestructura.cpms.cargar_catalogo_cpms import CargarCatalogoCpms
from app.infraestructura.cpms.configuracion_motor import cargar_configuracion_motor
from app.infraestructura.cpms.indice import obtener_motor_vigente
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_cpms_sql import (
    ErrorRepositorioCpms,
    RepositorioCpmsSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

_RUTA_INDICE = RAIZ_BACKEND / ".cache" / "motor_cpms" / "indice.joblib"


def obtener_repositorio_cpms(sesion: AsyncSession = Depends(obtener_sesion)) -> RepositorioCpms:
    return RepositorioCpmsSql(sesion)


def obtener_registro_mediciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RegistroMediciones:
    return RegistroMedicionesSql(sesion)


async def obtener_motor_sugerencia(
    repositorio: RepositorioCpms = Depends(obtener_repositorio_cpms),
) -> MotorSugerenciaCpms:
    """Reconstruye el indice solo si la version vigente cambio desde la
    ultima vez que se guardo en disco (Seccion 8.2, punto 7: `obtener_motor_vigente`,
    ya escrito en la Fase 9 para `herramientas/evaluar_motor_cpms.py`, y
    reutilizado aqui sin cambios)."""

    configuracion = cargar_configuracion_motor()
    try:
        return await obtener_motor_vigente(repositorio, _RUTA_INDICE, configuracion)
    except ErrorRepositorioCpms as error:
        raise ErrorAplicacion(
            "CATALOGO_CPMS_VACIO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error


def construir_sugerir_codigo_cpms(
    motor: MotorSugerenciaCpms = Depends(obtener_motor_sugerencia),
    repositorio: RepositorioCpms = Depends(obtener_repositorio_cpms),
    registro_mediciones: RegistroMediciones = Depends(obtener_registro_mediciones),
    reloj: Reloj = Depends(obtener_reloj),
) -> SugerirCodigoCpms:
    return SugerirCodigoCpms(motor, repositorio, registro_mediciones, reloj)


def construir_confirmar_codigo_cpms(
    repositorio: RepositorioCpms = Depends(obtener_repositorio_cpms),
    registro_mediciones: RegistroMediciones = Depends(obtener_registro_mediciones),
    reloj: Reloj = Depends(obtener_reloj),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> ConfirmarCodigoCpms:
    return ConfirmarCodigoCpms(
        repositorio, registro_mediciones, reloj, RepositorioEstadoCuentaSql(sesion)
    )


def construir_listar_versiones_cpms(
    repositorio: RepositorioCpms = Depends(obtener_repositorio_cpms),
) -> ListarVersionesCpms:
    return ListarVersionesCpms(repositorio)


def construir_cargar_catalogo_cpms(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> CargarCatalogoCpms:
    return CargarCatalogoCpms(sesion)
