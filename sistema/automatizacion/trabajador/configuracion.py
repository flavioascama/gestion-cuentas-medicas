"""Configuracion del trabajador, leida de variables de entorno.

Reutiliza `app.compartido.rutas.RAIZ_BACKEND` (del backend, importado como
dependencia de ruta -- ver pyproject.toml) para resolver
configuracion/selectores/acredita_salud.yaml en el mismo lugar donde ya
vive: no hace falta una variable de entorno nueva para eso, a diferencia
de docs/fuentes/ o reportes/ (Fase 4), porque este proceso SI tiene el
arbol completo de sistema/backend/ copiado en su propia imagen (Dockerfile
de este mismo directorio), no solo sistema/backend/app/.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.compartido.rutas import RAIZ_BACKEND


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.environ.get(nombre)
    return int(valor) if valor else por_defecto


def _secreto(nombre: str) -> str:
    """RNF-11 y C-06: las claves no tienen valor por defecto en el codigo
    versionado; si falta alguna en el entorno (.env), el trabajador no
    arranca."""
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta {nombre} en el entorno (.env).")
    return valor


class Configuracion:
    url_base_datos: str = _secreto("URL_BASE_DATOS")

    acredita_salud_url_base: str = os.environ.get(
        "ACREDITA_SALUD_URL_BASE", "http://localhost:8100"
    )
    acredita_salud_usuario: str = os.environ.get("ACREDITA_SALUD_USUARIO", "ipress_demo")
    acredita_salud_clave: str = _secreto("ACREDITA_SALUD_CLAVE")

    # Validador TEDEF Web (Fase 14/16, Seccion 9.2), mismo patron que
    # ACREDITA SALUD arriba.
    tedef_web_url_base: str = os.environ.get("TEDEF_WEB_URL_BASE", "http://localhost:8102")
    tedef_web_usuario: str = os.environ.get("TEDEF_WEB_USUARIO", "validador_ipress_demo")
    tedef_web_clave: str = _secreto("TEDEF_WEB_CLAVE")
    # Seccion 9.2, punto 4: tiempo limite esperando "Validando lote" en
    # segundo plano (bastante mayor que
    # VALIDACION_SEGUNDO_PLANO_SEGUNDOS del simulador, que solo fija
    # cuanto tarda EL SIMULADOR en resolver, no cuanto espera el robot).
    tiempo_limite_validacion_segundos: int = _entero("TIEMPO_LIMITE_VALIDACION_SEGUNDOS", 60)
    intervalo_poll_validacion_segundos: int = _entero("INTERVALO_POLL_VALIDACION_SEGUNDOS", 3)

    # Portal de respuestas del simulador receptor IAFAS (Fase 8/12,
    # Seccion 8.3): puerto HTTP interno de contenedor, sin sesion.
    receptor_iafas_url_base: str = os.environ.get(
        "RECEPTOR_IAFAS_URL_BASE", "http://localhost:8101"
    )
    # Seccion 8.3, punto 3: intervalo con el que el robot de monitoreo se
    # reencola mientras el receptor todavia no publico respuesta.
    intervalo_reconsulta_monitoreo_minutos: int = _entero(
        "INTERVALO_RECONSULTA_MONITOREO_MINUTOS", 15
    )

    # Comunicaciones de la IAFAS (2026-11-13): bandeja de correo de la
    # clinica, leida por IMAP. Sin host, el robot solo revisa el portal.
    correo_imap_host: str = os.environ.get("CORREO_IMAP_HOST", "")
    correo_imap_puerto: int = _entero("CORREO_IMAP_PUERTO", 993)
    correo_imap_usuario: str = os.environ.get("CORREO_IMAP_USUARIO", "")
    correo_imap_clave: str = os.environ.get("CORREO_IMAP_CLAVE", "")
    correo_imap_tls: bool = os.environ.get("CORREO_IMAP_TLS", "true").lower() == "true"

    # Seccion 8.1: 'el navegador se reinicia cada N trabajos... o ante
    # error irrecuperable'.
    reinicios_navegador_cada_n_trabajos: int = _entero("REINICIOS_NAVEGADOR_CADA_N_TRABAJOS", 20)

    # Seccion 8.1, punto 6: 'reintenta con retroceso exponencial hasta el
    # maximo configurado'. Se aplica solo a fallos genuinos (excepciones);
    # el reencolado sin error de MONITOREAR_RESPUESTA_IAFAS usa su propio
    # intervalo de arriba, no este backoff.
    maximo_intentos: int = _entero("MAXIMO_INTENTOS_TRABAJO", 5)
    backoff_base_segundos: int = _entero("BACKOFF_BASE_SEGUNDOS", 30)

    intervalo_poll_segundos: int = _entero("INTERVALO_POLL_SEGUNDOS", 5)

    # Seccion 8.4 (Fase 15): protocolo de sesion asistida con CAPTCHA.
    ruta_sesiones_plataformas: Path = Path(
        os.environ.get("RUTA_SESIONES_PLATAFORMAS", "/sesiones_plataformas")
    )
    # Clave Fernet (cryptography.fernet.Fernet.generate_key()) para cifrar
    # el storage_state guardado en ese volumen (punto 4: "guarda el estado
    # de sesion de Playwright... cifrado"). El valor de ejemplo NO sirve
    # para produccion -- ver .env.ejemplo.
    clave_cifrado_sesiones: str = _secreto("CLAVE_CIFRADO_SESIONES")
    # C-12 y RNF-16: clave Fernet propia de las evidencias del robot.
    clave_cifrado_evidencias: str = _secreto("CLAVE_CIFRADO_EVIDENCIAS")
    # Punto 4: "espera con un tiempo limite configurable (por defecto 120
    # segundos)" la respuesta humana a un CAPTCHA.
    tiempo_limite_captcha_segundos: int = _entero("TIEMPO_LIMITE_CAPTCHA_SEGUNDOS", 120)
    intervalo_poll_captcha_segundos: int = _entero("INTERVALO_POLL_CAPTCHA_SEGUNDOS", 2)
    # Punto 5: "hasta tres intentos; luego FALLIDA".
    max_intentos_captcha: int = _entero("MAXIMO_INTENTOS_CAPTCHA", 3)
    # Cuanto dura ACTIVA una sesion asistida antes de expirar (no esta en
    # el manual de ninguna plataforma real -- Seccion 16, supuesto 7 del
    # plan: "tiempo de vida de sesion de los simuladores: configurable; no
    # esta publicado para las plataformas reales").
    duracion_sesion_plataforma_minutos: int = _entero("DURACION_SESION_PLATAFORMA_MINUTOS", 30)

    ruta_reportes: Path = Path(os.environ.get("RUTA_REPORTES", "/reportes"))
    # Seccion 8.3 (Fase 16): volumen de artefactos donde
    # CargarLoteEnValidador escribe el `.S01` descargado; RemitirLote
    # (backend) lo lee del mismo volumen (docker-compose.yml de la raiz).
    ruta_artefactos_s01: Path = Path(os.environ.get("RUTA_ARTEFACTOS_S01", "/artefactos_s01"))

    raiz_backend: Path = RAIZ_BACKEND


def exigir_tls(cfg: Configuracion, entorno: str) -> None:
    """C-04 y RNF-15 (2026-11-13): fuera de desarrollo, las plataformas por
    https y la base con conexion cifrada; si no, el trabajador no arranca."""
    if entorno == "desarrollo":
        return
    urls = (
        ("ACREDITA_SALUD_URL_BASE", cfg.acredita_salud_url_base),
        ("TEDEF_WEB_URL_BASE", cfg.tedef_web_url_base),
        ("RECEPTOR_IAFAS_URL_BASE", cfg.receptor_iafas_url_base),
    )
    sin_tls = [alias for alias, url in urls if not url.startswith("https://")]
    if "ssl=" not in cfg.url_base_datos:
        sin_tls.append("URL_BASE_DATOS (ssl=require)")
    if cfg.correo_imap_host and not cfg.correo_imap_tls:
        sin_tls.append("CORREO_IMAP_TLS")
    if sin_tls:
        raise RuntimeError("Canales sin TLS fuera de desarrollo: " + ", ".join(sin_tls))


configuracion = Configuracion()
exigir_tls(configuracion, os.environ.get("ENTORNO", "desarrollo"))
