"""Carga configuracion/tedef/tablas_activas.yaml (Seccion 8.1 del plan v3):
que tablas incluye GenerarLote en cada lote. Si el archivo pide una tabla
que el generador todavia no implementa, falla al arrancar en vez de
generar un lote incompleto en silencio."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.compartido.rutas import RAIZ_BACKEND

RUTA_TABLAS_ACTIVAS = RAIZ_BACKEND / "configuracion" / "tedef" / "tablas_activas.yaml"

# Unicas tablas que GenerarLote sabe construir hoy (Seccion 8.1).
TABLAS_IMPLEMENTADAS = ("T1", "T2", "T3", "T4")


class ErrorTablaActivaNoImplementada(Exception):
    pass


@lru_cache
def cargar_tablas_activas(ruta: Path = RUTA_TABLAS_ACTIVAS) -> tuple[str, ...]:
    with ruta.open(encoding="utf-8") as archivo:
        tablas = tuple(yaml.safe_load(archivo))

    no_implementadas = [t for t in tablas if t not in TABLAS_IMPLEMENTADAS]
    if no_implementadas:
        raise ErrorTablaActivaNoImplementada(
            f"tablas_activas.yaml pide {no_implementadas}, que GenerarLote todavia no "
            "implementa (Seccion 8.1: T4 se agrega en la Fase 17)."
        )
    return tablas
