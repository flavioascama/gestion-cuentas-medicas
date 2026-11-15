"""Pruebas del cargador CPMS (Seccion 8.2): lectura del archivo real y
carga en base de datos con huella y version."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_cpms import CpmsProcedimientoModelo, CpmsVersionModelo
from herramientas.cargar_cpms import (
    CARPETA_FUENTES,
    _cargar,
    _descubrir_partes,
    _leer_procedimientos,
)

_ARCHIVO_PARTE1 = (
    CARPETA_FUENTES
    / "Parte_1_050623_Anexo_Nro_1_Listado_de_Procedimientos_Medicos_y_Sanitarios_ok15.xlsx"
)


def prueba_leer_procedimientos_devuelve_12002_filas_sin_nulos() -> None:
    procedimientos = _leer_procedimientos(_ARCHIVO_PARTE1)

    assert len(procedimientos) == 12002
    assert all(all(valor for valor in fila.values()) for fila in procedimientos)
    codigos = {fila["codigo_procedimiento"] for fila in procedimientos}
    assert len(codigos) == 12002  # ningun duplicado


def prueba_descubrir_partes_encuentra_el_archivo_versionado() -> None:
    partes = _descubrir_partes()
    assert _ARCHIVO_PARTE1 in partes


async def prueba_cargar_crea_version_con_huella_y_procedimientos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    version_id = await _cargar([_ARCHIVO_PARTE1], "version-de-prueba", fabrica_sesiones)

    async with fabrica_sesiones() as sesion:
        version = await sesion.get(CpmsVersionModelo, version_id)
        assert version is not None
        assert version.etiqueta == "version-de-prueba"
        assert version.conteo == 12002
        assert version.archivos_origen[0]["archivo"] == _ARCHIVO_PARTE1.name
        assert len(version.archivos_origen[0]["huella_sha256"]) == 64  # sha256 en hex

        total = await sesion.scalar(
            sa.select(sa.func.count())
            .select_from(CpmsProcedimientoModelo)
            .where(CpmsProcedimientoModelo.cpms_version_id == version_id)
        )
        assert total == 12002
