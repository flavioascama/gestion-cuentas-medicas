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


class Configuracion:
    usuario: str = os.environ.get("TEDEF_WEB_USUARIO", "validador_ipress_demo")
    clave: str = os.environ.get("TEDEF_WEB_CLAVE", "")

    puerto: int = _entero("PUERTO", 8000)
    sesion_expiracion_minutos: int = _entero("SESION_EXPIRACION_MINUTOS", 30)
    validacion_segundo_plano_segundos: int = _entero("VALIDACION_SEGUNDO_PLANO_SEGUNDOS", 3)
    latencia_artificial_ms: int = _entero("LATENCIA_ARTIFICIAL_MS", 0)

    # 'ninguno' | 'forzar_observaciones' | 'forzar_error_validacion' (Seccion
    # 9.2: "ruta de administracion para forzar observaciones o errores en un
    # lote, para pruebas deterministas"). El valor de arranque es esta
    # variable; la ruta de administracion lo puede cambiar despues en
    # caliente (ver app/estado_falla.py).
    modo_falla_inicial: str = os.environ.get("MODO_FALLA", "ninguno")

    # Fase 20: mismo mecanismo que simuladores/acredita_salud (Seccion 8.4:
    # "los simuladores exponen una ruta de administracion que devuelve el
    # texto del CAPTCHA vigente solo si SIMULADOR_MODO_PRUEBA=true"). Sin
    # esto, ninguna prueba de integracion puede resolver el CAPTCHA de
    # sesion asistida de TEDEF Web por la API, sin abrir un navegador.
    simulador_modo_prueba: bool = os.environ.get("SIMULADOR_MODO_PRUEBA", "false").lower() == "true"

    datos_semilla: Path = Path(os.environ.get("RUTA_SIMULADORES_DATOS_SEMILLA", "/datos_semilla"))
    docs_fuentes: Path = Path(os.environ.get("RUTA_DOCS_FUENTES", "/docs_fuentes"))
    maestros_sinteticos: Path = Path(
        os.environ.get("RUTA_MAESTROS_SINTETICOS", "/maestros_sinteticos")
    )
    base_datos: Path = Path(os.environ.get("BASE_DATOS", "/datos/tedef_web.sqlite3"))
    directorio_lotes: Path = Path(os.environ.get("DIRECTORIO_LOTES", "/datos/lotes"))


configuracion = Configuracion()
