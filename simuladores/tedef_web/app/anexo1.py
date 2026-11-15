"""Lectura independiente del Anexo 1 (Seccion 9.2: "implementacion propia
e independiente que lee directamente el Anexo 1 desde docs/fuentes/...
sin usar el YAML ni el codigo del backend"). Escrita desde cero a partir
de la misma hoja de calculo publica que usa
sistema/backend/herramientas/extraer_esquema_tedef.py, sin importar ese
modulo ni su YAML derivado (Regla 12: la validacion del simulador es
independiente de la del backend).

Alcance: T1, T2, T3 y T4 -- las tablas que el backend genera hoy (decision
propia de este simulador, documentada en docs/DECISIONES.md, Fases 14 y
17; no depende de configuracion/tedef/tablas_activas.yaml del backend,
que este simulador no lee).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import xlrd

_ARCHIVO_ANEXO1 = "Anexo-1_tedef-ipress-iafas_octubre_2025.xls"

# (id de tabla, nombre de hoja en el .xls, prefijo del archivo plano,
# longitud de registro) -- verificado contra el propio archivo.
_TABLAS = (
    ("T1", "T1-Documento Facturador", "dfac", 242),
    ("T2", "T2-Car Gen de la Prestación", "date", 410),
    ("T3", "T3-Detalle de Servicios", "dser", 244),
    ("T4", "T4-Productos de Farmacia", "dfar", 146),
)


@dataclass(frozen=True, slots=True)
class CampoAnexo1:
    numero: int
    nombre: str
    obligatorio: bool
    longitud: int
    posicion_inicial: int
    criterios_texto: str


@dataclass(frozen=True, slots=True)
class TablaAnexo1:
    id: str
    prefijo: str
    longitud_registro: int
    campos: tuple[CampoAnexo1, ...]


def _obligatorio_de_campo(valor: object) -> bool:
    return str(valor).strip().upper() == "SI"


def _es_fila_de_campo(valor: object) -> bool:
    return isinstance(valor, float) and valor == int(valor)


def _extraer_campos(hoja: xlrd.sheet.Sheet) -> tuple[CampoAnexo1, ...]:
    campos = [
        CampoAnexo1(
            numero=int(hoja.cell_value(fila, 0)),
            nombre=str(hoja.cell_value(fila, 1)).strip(),
            obligatorio=_obligatorio_de_campo(hoja.cell_value(fila, 4)),
            longitud=int(hoja.cell_value(fila, 5)),
            posicion_inicial=int(hoja.cell_value(fila, 7)),
            criterios_texto=str(hoja.cell_value(fila, 3)).strip(),
        )
        for fila in range(hoja.nrows)
        if _es_fila_de_campo(hoja.cell_value(fila, 0))
    ]
    return tuple(sorted(campos, key=lambda campo: campo.numero))


@lru_cache
def cargar_tablas(ruta_docs_fuentes: Path) -> dict[str, TablaAnexo1]:
    libro = xlrd.open_workbook(str(ruta_docs_fuentes / _ARCHIVO_ANEXO1))
    tablas = {}
    for tabla_id, nombre_hoja, prefijo, longitud_registro in _TABLAS:
        hoja = libro.sheet_by_name(nombre_hoja)
        tablas[tabla_id] = TablaAnexo1(
            id=tabla_id,
            prefijo=prefijo,
            longitud_registro=longitud_registro,
            campos=_extraer_campos(hoja),
        )
    return tablas
