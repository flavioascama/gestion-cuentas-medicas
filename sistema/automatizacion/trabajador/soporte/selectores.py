"""Carga configuracion/selectores/acredita_salud.yaml (Seccion 8.1:
'selectores... nunca en el codigo'). Sin biblioteca de tipos propia: cada
robot conoce las claves que necesita y falla con un mensaje explicito si
falta una (Seccion 8.1: 'falla con mensaje explicito si un selector no
existe')."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from trabajador.configuracion import configuracion

RUTA_SELECTORES_ACREDITA_SALUD = (
    configuracion.raiz_backend / "configuracion" / "selectores" / "acredita_salud.yaml"
)
RUTA_SELECTORES_TEDEF_WEB = (
    configuracion.raiz_backend / "configuracion" / "selectores" / "tedef_web.yaml"
)

# Seccion 8.4 (Fase 15): el robot de sesion asistida es el mismo para
# cualquier plataforma, pero cada una tiene su propio archivo de
# selectores. TEDEF Web se agrega en la Fase 16.
_RUTAS_SELECTORES_POR_PLATAFORMA = {
    "acredita_salud": RUTA_SELECTORES_ACREDITA_SALUD,
    "tedef_web": RUTA_SELECTORES_TEDEF_WEB,
}


class ErrorSelectorNoEncontrado(Exception):
    pass


def ruta_selectores(plataforma: str) -> Path:
    try:
        return _RUTAS_SELECTORES_POR_PLATAFORMA[plataforma]
    except KeyError as error:
        raise ErrorSelectorNoEncontrado(
            f"No hay archivo de selectores para la plataforma {plataforma!r} todavia."
        ) from error


@lru_cache
def _cargar(ruta: Path) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        contenido: dict[str, Any] = yaml.safe_load(archivo)
    return contenido


def obtener_selector(seccion: str, clave: str, ruta: Path = RUTA_SELECTORES_ACREDITA_SALUD) -> str:
    datos = _cargar(ruta)
    try:
        valor = datos[seccion][clave]
    except KeyError as error:
        raise ErrorSelectorNoEncontrado(
            f"No existe el selector '{seccion}.{clave}' en {ruta}."
        ) from error
    if not isinstance(valor, str):
        raise ErrorSelectorNoEncontrado(
            f"El selector '{seccion}.{clave}' en {ruta} no es una cadena: {valor!r}."
        )
    return valor
