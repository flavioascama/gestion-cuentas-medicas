"""Lectura de los archivos fuente del catalogo CPMS ('Parte_N_...xlsx',
Seccion 8.2): extraido de `herramientas/cargar_cpms.py` (Fase 4) para que
tanto ese script como `CargarCatalogoCpms` (Fase 18, `POST
/catalogo-cpms/versiones`) lean el mismo archivo con la misma logica, sin
que `app/` dependa de `herramientas/` (la direccion de dependencia
correcta es la inversa: herramientas ya importa de `app`)."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any

import openpyxl

from app.compartido.rutas import raiz_docs_fuentes

_NOMBRE_HOJA = "Parte 1"  # todas las partes publicadas usan este nombre de hoja


def leer_procedimientos(ruta: Path | IO[bytes]) -> list[dict[str, Any]]:
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = libro[_NOMBRE_HOJA]
    filas = hoja.iter_rows(values_only=True)
    next(filas)  # fila 1: titulo del anexo
    next(filas)  # fila 2: encabezado de columnas
    procedimientos = []
    for fila in filas:
        if fila[0] is None:
            continue
        procedimientos.append(
            {
                "codigo_grupo": str(fila[1]).strip(),
                "nombre_grupo": str(fila[2]).strip(),
                "codigo_seccion": str(fila[3]).strip(),
                "nombre_seccion": str(fila[4]).strip(),
                "codigo_subseccion": str(fila[5]).strip(),
                "nombre_subseccion": str(fila[6]).strip(),
                "codigo_procedimiento": str(fila[7]).strip(),
                "denominacion_procedimiento": str(fila[8]).strip(),
            }
        )
    return procedimientos


def descubrir_partes() -> list[Path]:
    return sorted(raiz_docs_fuentes().glob("Parte_*.xlsx"))
