"""Resolucion de rutas fuera de sistema/backend/, compartidas por las
herramientas de extraccion y generacion (esquema TEDEF, criterios, CPMS,
datos sinteticos).

No se asume que el proceso corre con el repositorio completo en disco: el
contenedor del backend (Dockerfile, docker-compose.yml) solo trae
sistema/backend/, no la raiz del repositorio, por lo que docs/fuentes/ y
simuladores/datos_semilla/ no existen en la misma posicion relativa dentro
del contenedor. Las variables de entorno RUTA_DOCS_FUENTES y
RUTA_SIMULADORES_DATOS_SEMILLA permiten apuntar a donde sea que se hayan
montado (ver los volumenes del servicio backend); en desarrollo local sin
Docker, se usa por defecto la posicion real del repositorio.
"""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

RAIZ_BACKEND = Path(__file__).resolve().parents[2]  # sistema/backend/


def _resolver(variable_entorno: str, ruta_relativa_local: str) -> Path:
    variable = os.environ.get(variable_entorno)
    if variable:
        return Path(variable)
    # Supuesto de desarrollo local: el repositorio completo esta en disco y
    # sistema/backend/ tiene la raiz del repo dos niveles arriba. Calculado
    # aqui adentro, no al importar el modulo, porque dentro del contenedor
    # (donde este supuesto no vale) la variable de entorno siempre esta
    # definida y esta rama nunca se ejecuta.
    return RAIZ_BACKEND.parents[1] / ruta_relativa_local


def raiz_docs_fuentes() -> Path:
    return _resolver("RUTA_DOCS_FUENTES", "docs/fuentes")


def raiz_simuladores_datos_semilla() -> Path:
    return _resolver("RUTA_SIMULADORES_DATOS_SEMILLA", "simuladores/datos_semilla")


def raiz_reportes() -> Path:
    return _resolver("RUTA_REPORTES", "reportes")


def raiz_frontend() -> Path:
    return _resolver("RUTA_FRONTEND", "sistema/frontend")


def raiz_artefactos_s01() -> Path:
    """Volumen donde vive el `.S01` de cada lote (Fase 16): lo escribe el
    trabajador al descargarlo del validador y, en modo de contingencia,
    el backend al recibirlo del analista."""
    return _resolver("RUTA_ARTEFACTOS_S01", "artefactos_s01")


def ruta_local_s01(ruta_guardada: str) -> Path:
    """Ruta del `.S01` de un lote tal como la ve este proceso.

    La carpeta de artefactos es una sola, pero cada proceso la ve en un
    lugar distinto: el servidor y el robot del contenedor en
    /artefactos_s01, y el robot con ventana, que corre en la computadora
    fuera de Docker, en la carpeta del proyecto. La ruta guardada es la
    de quien escribio el archivo: si este proceso no la encuentra tal
    cual, busca el mismo nombre en su propia carpeta de artefactos."""
    directa = Path(ruta_guardada)
    if directa.is_file():
        return directa
    # PureWindowsPath entiende los dos separadores, / y \\.
    return raiz_artefactos_s01() / PureWindowsPath(ruta_guardada).name
