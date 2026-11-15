"""Configuracion del simulador, leida de variables de entorno.

Aplicacion independiente (Regla 0.5): no importa nada de sistema/backend/,
asi que no comparte el modulo Configuracion del backend aunque el patron
sea el mismo (pydantic-settings no es dependencia de este simulador
justamente para mantenerlo minimo; se usa os.environ directo).
"""

from __future__ import annotations

import os
from pathlib import Path


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.environ.get(nombre)
    return int(valor) if valor else por_defecto


class Configuracion:
    portal_puerto: int = _entero("PORTAL_PUERTO", 8000)
    base_datos: Path = Path(os.environ.get("BASE_DATOS", "/datos/pse.sqlite3"))


configuracion = Configuracion()
