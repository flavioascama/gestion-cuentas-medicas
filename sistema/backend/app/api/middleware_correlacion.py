"""Middleware que asigna un identificador de correlacion por solicitud.

Se enlaza a structlog.contextvars para que todo log emitido durante el
procesamiento de la solicitud incluya 'correlacion_id' sin pasarlo a mano
por cada llamada (Seccion 11).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

CabeceraCorrelacion = "X-Correlacion-Id"


async def middleware_correlacion(
    solicitud: Request, siguiente: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlacion_id = solicitud.headers.get(CabeceraCorrelacion, str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlacion_id=correlacion_id)
    try:
        respuesta = await siguiente(solicitud)
    finally:
        structlog.contextvars.unbind_contextvars("correlacion_id")
    respuesta.headers[CabeceraCorrelacion] = correlacion_id
    return respuesta
