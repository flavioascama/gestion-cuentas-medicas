"""Configuracion del simulador, leida de variables de entorno.

Aplicacion independiente (Regla 0.5): no importa nada de sistema/backend/.
"""

from __future__ import annotations

import os


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.environ.get(nombre)
    return int(valor) if valor else por_defecto


class Configuracion:
    portal_puerto: int = _entero("PORTAL_PUERTO", 8000)
    clave_api: str = os.environ.get("CLAVE_API_SISTEMA_HOSPITALARIO", "")


configuracion = Configuracion()
