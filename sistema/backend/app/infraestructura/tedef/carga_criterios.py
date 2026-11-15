"""Carga configuracion/reglas_tedef/criterios.csv (Seccion 7.4)."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from app.compartido.rutas import RAIZ_BACKEND
from app.dominio.integracion.criterios import CriterioRegla

RUTA_CRITERIOS = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "criterios.csv"


@lru_cache
def cargar_criterios(ruta: Path = RUTA_CRITERIOS) -> tuple[CriterioRegla, ...]:
    with ruta.open(encoding="utf-8", newline="") as archivo:
        filas = csv.DictReader(archivo)
        return tuple(
            CriterioRegla(
                tabla=fila["tabla"],
                campo_numero=int(fila["campo_numero"]),
                campo_nombre=fila["campo_nombre"],
                criterio_id=fila["criterio_id"],
                texto_literal=fila["texto_literal"],
                implementada=fila["implementada"].strip().lower() == "si",
                regla=fila["regla"],
            )
            for fila in filas
        )
