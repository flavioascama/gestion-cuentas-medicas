"""Carga configuracion/esquema_tedef/esquema_2025_10.yaml (Seccion 7.1).

El sistema en ejecucion lee unicamente este YAML, nunca el .xls (Regla
0.1). Este modulo es el unico lugar donde se abre ese archivo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.compartido.rutas import RAIZ_BACKEND
from app.dominio.integracion.esquema import CampoEsquema, TablaEsquema

RUTA_ESQUEMA = RAIZ_BACKEND / "configuracion" / "esquema_tedef" / "esquema_2025_10.yaml"


def _construir_tabla(datos: dict[str, Any]) -> TablaEsquema:
    campos = tuple(
        CampoEsquema(
            numero=c["numero"],
            nombre=c["nombre"],
            obligatorio=c["obligatorio"],
            longitud=c["longitud"],
            decimales=c["decimales"],
            posicion_inicial=c["posicion_inicial"],
        )
        for c in datos["campos"]
    )
    return TablaEsquema(
        id=datos["id"],
        nombre=datos["nombre"],
        prefijo=datos["prefijo"],
        obligatoria=datos["obligatoria"],
        condicional=datos["condicional"],
        longitud_registro=datos["longitud_registro"],
        campos=campos,
    )


@lru_cache
def version_esquema(ruta: Path = RUTA_ESQUEMA) -> str:
    """RT-06: la version del estandar TEDEF que declara el propio YAML."""

    with ruta.open(encoding="utf-8") as archivo:
        return str(yaml.safe_load(archivo)["version"])


@lru_cache
def cargar_esquema(ruta: Path = RUTA_ESQUEMA) -> dict[str, TablaEsquema]:
    """{id_tabla: TablaEsquema}, para las 8 tablas del Anexo 1."""

    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)
    return {t["id"]: _construir_tabla(t) for t in datos["tablas"]}
