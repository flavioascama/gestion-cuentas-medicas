"""Configuracion del simulador, leida de variables de entorno.

Aplicacion independiente (Regla 0.5): no importa nada de sistema/backend/,
por eso no comparte el modulo Configuracion del backend aunque el patron
sea el mismo.
"""

from __future__ import annotations

import os
from pathlib import Path


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.environ.get(nombre)
    return int(valor) if valor else por_defecto


def _booleano(nombre: str, por_defecto: bool) -> bool:
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí")


class Configuracion:
    usuario: str = os.environ.get("ACREDITA_SALUD_USUARIO", "ipress_demo")
    clave: str = os.environ.get("ACREDITA_SALUD_CLAVE", "")
    perfil_carga_masiva: bool = _booleano("ACREDITA_SALUD_PERFIL_CARGA_MASIVA", True)
    # La sesion iniciada representa a UNA IPRESS (la clinica que opera el
    # sistema, Seccion 6.1); toda acreditacion generada en esa sesion queda
    # asociada a este codigo sintetico de 8 caracteres.
    ipress_codigo: str = os.environ.get("IPRESS_CODIGO_SIMULADO", "12345678")

    puerto: int = _entero("PUERTO", 8000)
    sesion_expiracion_minutos: int = _entero("SESION_EXPIRACION_MINUTOS", 30)
    latencia_artificial_ms: int = _entero("LATENCIA_ARTIFICIAL_MS", 0)

    # 'ninguno' | 'caida_servicio' | 'expiracion_sesion' | 'respuesta_vacia'
    # (Seccion 9.1: 'modo de falla inducida activable por variable de
    # entorno o por una ruta de administracion'). El valor de arranque es
    # esta variable; la ruta de administracion lo puede cambiar despues en
    # caliente (ver app/estado_falla.py).
    modo_falla_inicial: str = os.environ.get("MODO_FALLA", "ninguno")

    # Seccion 8.4: "los simuladores exponen una ruta de administracion que
    # devuelve el texto del CAPTCHA vigente solo si
    # SIMULADOR_MODO_PRUEBA=true; la prueba actua como el usuario humano
    # llamando a la API del sistema, nunca el robot". Por defecto False:
    # la ruta no responde salvo que se active a proposito.
    simulador_modo_prueba: bool = _booleano("SIMULADOR_MODO_PRUEBA", False)

    datos_semilla: Path = Path(os.environ.get("RUTA_SIMULADORES_DATOS_SEMILLA", "/datos_semilla"))
    base_datos: Path = Path(os.environ.get("BASE_DATOS", "/datos/acredita_salud.sqlite3"))


configuracion = Configuracion()
