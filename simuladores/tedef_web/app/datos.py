"""Carga de datos sinteticos (Seccion 3.3, Seccion 9.2).

`maestro_iafas.csv` y `maestro_ipress.csv` son la misma fuente que usa el
backend para poblar Postgres (sistema/backend/herramientas/
cargar_cuentas_sinteticas.py): archivos de DATOS deterministas, no de
codigo, montados de solo lectura (Regla 0.5 prohibe compartir codigo, no
un archivo de datos versionado). Usar exactamente esa fuente es lo que
permite que "la entidad" y el "maestro de IAFAS" de este simulador
coincidan con los de un lote real generado por el backend -- ver
docs/DECISIONES.md, Fase 14.

`claves_iafas.json` es la contrasena ficticia por IAFAS (Seccion 9.2,
Seccion 9.3), compartida solo con simuladores/receptor_iafas/. El backend
no la lee (regla 11).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IpressPropia:
    ruc: str
    codigo_ipress: str
    razon_social: str


@dataclass(frozen=True, slots=True)
class MaestroIafas:
    codigo: str
    razon_social: str


def _leer_csv_con_cabecera(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as archivo:
        lineas = [linea for linea in archivo if not linea.startswith("#")]
    return list(csv.DictReader(lineas))


def cargar_ipress_propia(ruta_maestros_sinteticos: Path) -> IpressPropia:
    """La primera fila de maestro_ipress.csv es la clinica que opera el
    sistema (mismo criterio que cargar_cuentas_sinteticas.py del backend:
    "indice == 0 -- la primera fila representa la clinica que opera el
    sistema")."""

    filas = _leer_csv_con_cabecera(ruta_maestros_sinteticos / "maestro_ipress.csv")
    primera = filas[0]
    return IpressPropia(
        ruc=primera["ruc"],
        codigo_ipress=primera["codigo_ipress"],
        razon_social=primera["razon_social"],
    )


def cargar_maestro_iafas(ruta_maestros_sinteticos: Path) -> tuple[MaestroIafas, ...]:
    filas = _leer_csv_con_cabecera(ruta_maestros_sinteticos / "maestro_iafas.csv")
    return tuple(MaestroIafas(codigo=f["codigo"], razon_social=f["razon_social"]) for f in filas)


def cargar_claves_iafas(ruta_datos_semilla: Path) -> dict[str, str]:
    contenido = json.loads((ruta_datos_semilla / "claves_iafas.json").read_text(encoding="utf-8"))
    claves: dict[str, str] = contenido["claves"]
    return claves
