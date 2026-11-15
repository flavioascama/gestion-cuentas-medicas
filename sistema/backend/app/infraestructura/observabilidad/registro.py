"""Registro estructurado en JSON, segun la Seccion 11 del plan.

Campos obligatorios en cada linea: instante, nivel, componente, caso_uso,
correlacion_id, actor, mensaje. `componente` se fija al obtener el logger.
`caso_uso`, `correlacion_id` y `actor` se enlazan por contexto (contextvars)
o se pasan explicitamente en cada llamada.

Prohibido registrar contraseñas, credenciales de portales o numeros de
documento completos (ver Seccion 11). Para numeros de documento, usar
`enmascarar` antes de incluirlos en un evento de log.

`obtener_registrador(componente)` es seguro de llamar a nivel de modulo
(patron habitual: `_registrador = obtener_registrador("mi.componente")` al
inicio del archivo), incluso antes de que `configurar_registro()` se haya
ejecutado. Por eso se usa `cache_logger_on_first_use=False`: structlog
resuelve la configuracion vigente en cada llamada a `.info()`/`.error()`,
no en el momento del `.bind()`. Con `True`, el primer `.bind()` de un modulo
importado antes de `configurar_registro()` queda fijado con la
configuracion por defecto (ConsoleRenderer) para siempre, y el proyecto
tiene demasiados modulos futuros creando su logger al importarse como para
garantizar el orden de import.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog


def _renombrar_claves_al_espanol(
    _logger: Any, _nombre_metodo: str, datos_evento: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog produce 'event' y 'level'; el plan exige 'mensaje' y 'nivel'."""

    if "event" in datos_evento:
        datos_evento["mensaje"] = datos_evento.pop("event")
    if "level" in datos_evento:
        datos_evento["nivel"] = datos_evento.pop("level")
    return datos_evento


def configurar_registro(nivel: str = "INFO") -> None:
    """Configura structlog para emitir JSON por stdout. Llamar una vez al arrancar."""

    nivel_numerico = getattr(logging, nivel.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=nivel_numerico)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="instante"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _renombrar_claves_al_espanol,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(nivel_numerico),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def obtener_registrador(componente: str) -> structlog.typing.FilteringBoundLogger:
    """Devuelve un logger con el campo 'componente' fijo, listo para usar."""

    registrador: structlog.typing.FilteringBoundLogger = structlog.get_logger()
    return registrador.bind(componente=componente)


def enmascarar(valor: str) -> str:
    """Deja visibles solo los dos ultimos caracteres, exigido por la Seccion 11."""

    if len(valor) <= 2:
        return "*" * len(valor)
    return "*" * (len(valor) - 2) + valor[-2:]
