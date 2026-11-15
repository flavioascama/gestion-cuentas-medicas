"""Patron de nombrado del .S01 y de los archivos planos internos (Anexo 3,
hoja Estandares -- Seccion 2.2 del plan).

Duplicado deliberado de sistema/backend/app/infraestructura/tedef/nombrado.py:
Regla 0.5 prohibe que este simulador importe codigo de sistema/. Ambos
archivos derivan del mismo ejemplo literal del Anexo 3
('937_20100121809_00140456_20002_1234567_201606_20130605.S01') y deben
mantenerse iguales a mano si el patron cambia -- ver docs/DECISIONES.md,
Fase 8.
"""

from __future__ import annotations

import re

PATRON_NOMBRE_S01 = re.compile(
    r"^937_(?P<ruc>\d{11})_(?P<ipress>\d{8})_(?P<iafas>\d{5})_"
    r"(?P<lote>\d{7})_(?P<periodo>\d{6})_(?P<fecha>\d{8})\.S01$"
)


def nombre_archivo_txt_esperado(prefijo: str, componentes: dict[str, str]) -> str:
    """Reconstruye el nombre de un archivo plano interno a partir de los
    componentes extraidos del nombre del .S01 (mismo ruc/ipress/iafas/lote/
    periodo/fecha, solo cambia el prefijo de tabla)."""

    return (
        f"{prefijo}_{componentes['ruc']}_{componentes['ipress']}_{componentes['iafas']}_"
        f"{componentes['lote']}_{componentes['periodo']}_{componentes['fecha']}.txt"
    )
