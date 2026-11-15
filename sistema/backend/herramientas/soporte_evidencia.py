"""Utilidades compartidas por las herramientas `generar_evidencia_*.py`
(Seccion 13 del plan v3, que mantiene sin cambio la exigencia de la
Seccion 11 del v2): "todos los reportes incluyen una cabecera que declara
que la ejecucion se realizo sobre datos sinteticos y contra simuladores
locales, e indica la latencia artificial configurada en el simulador
durante esa ejecucion".

La latencia vive en el proceso de cada simulador (variable de entorno
`LATENCIA_ARTIFICIAL_MS`), no en este contenedor -- se lee por HTTP via
`GET /admin/configuracion` (agregada en la Fase 20 a acredita_salud y
tedef_web) en vez de asumir un valor fijo, para que la cabecera sea
verdad incluso si alguien cambio esa variable antes de esta ejecucion.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.compartido.configuracion import obtener_configuracion

_TIMEOUT_CONSULTA_SIMULADOR_SEGUNDOS = 3.0
_NO_DISPONIBLE = "no disponible (el simulador no respondio durante esta ejecucion)"


@dataclass(frozen=True, slots=True)
class CabeceraEvidencia:
    generado_en: datetime
    latencia_acredita_salud: str
    latencia_tedef_web: str

    def como_lineas_comentario_csv(self) -> list[str]:
        """Para archivos CSV: lineas `# ...` antes del encabezado de
        columnas real (no hay convencion universal de metadata en CSV;
        un lector humano -- a quien va dirigida esta evidencia -- las lee
        sin dificultad, y basta con saltarlas al reprocesar)."""

        return [
            f"# Generado: {self.generado_en.isoformat()}",
            "# Datos sinteticos, entorno de prueba (Docker local): ninguna fila proviene "
            "de una IAFAS, IPRESS o asegurado real.",
            f"# Latencia artificial configurada en ACREDITA SALUD: {self.latencia_acredita_salud}.",
            f"# Latencia artificial configurada en TEDEF Web: {self.latencia_tedef_web}.",
            "# El simulador receptor IAFAS no tiene latencia artificial configurable.",
        ]

    def como_lineas_markdown(self) -> list[str]:
        """Para archivos Markdown (`cobertura_reglas_tedef.md`): una
        blockquote antes del titulo principal del reporte."""

        return [
            f"> Generado: {self.generado_en.isoformat()}. Datos sinteticos, entorno de "
            "prueba (Docker local): ninguna fila proviene de una IAFAS, IPRESS o "
            "asegurado real.",
            f"> Latencia artificial configurada en ACREDITA SALUD: {self.latencia_acredita_salud}. "
            f"En TEDEF Web: {self.latencia_tedef_web}. El simulador receptor IAFAS no tiene "
            "latencia artificial configurable.",
            "",
        ]

    def como_diccionario(self) -> dict[str, str | bool]:
        """Para archivos JSON: una clave `_cabecera` al inicio del documento."""

        return {
            "generado_en": self.generado_en.isoformat(),
            "datos_sinteticos": True,
            "entorno": "prueba (Docker local): ninguna fila proviene de una IAFAS, "
            "IPRESS o asegurado real",
            "latencia_artificial_acredita_salud": self.latencia_acredita_salud,
            "latencia_artificial_tedef_web": self.latencia_tedef_web,
            "latencia_artificial_receptor_iafas": "no aplica (sin latencia configurable)",
        }


async def _latencia_simulador(url_base: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_CONSULTA_SIMULADOR_SEGUNDOS) as cliente:
            respuesta = await cliente.get(f"{url_base}/admin/configuracion")
            respuesta.raise_for_status()
            return f"{respuesta.json()['latencia_artificial_ms']} ms"
    except httpx.HTTPError:
        return _NO_DISPONIBLE


async def construir_cabecera_evidencia() -> CabeceraEvidencia:
    configuracion = obtener_configuracion()
    latencia_acredita_salud, latencia_tedef_web = await asyncio.gather(
        _latencia_simulador(configuracion.acredita_salud_url_base),
        _latencia_simulador(configuracion.tedef_web_url_base),
    )
    return CabeceraEvidencia(
        generado_en=datetime.now().astimezone(),
        latencia_acredita_salud=latencia_acredita_salud,
        latencia_tedef_web=latencia_tedef_web,
    )
