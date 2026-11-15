"""Temporizador del sistema (actor de CU-05 y CU-11, Tabla 51/Anexo C):
decide que tareas periodicas toca ejecutar y las ejecuta sin que una falla
detenga a las demas.

Hasta la verificacion de cumplimiento del 12 de noviembre, el control de
plazos (CU-11), el anclaje diario de la cadena de eventos y su
verificacion diaria (RNF-18, AD-11, C-10) existian como herramientas de
invocacion manual. Este modulo es la logica que las agenda; el proceso que
la corre en bucle es `herramientas/temporizador.py`, levantado como su
propio servicio en docker-compose.yml (AD-08). Sin dependencias de cron:
el intervalo se mide contra la ultima ejecucion de cada tarea, y al
arrancar el proceso se ejecutan todas una vez (las tres son idempotentes:
el control de plazos no repite avisos ya emitidos, el ancla del dia se
reescribe y la verificacion solo lee)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class TareaProgramada:
    nombre: str
    intervalo: timedelta
    ejecutar: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ResultadoTarea:
    nombre: str
    exitosa: bool
    error: str | None = None


def tareas_pendientes(
    tareas: list[TareaProgramada], ultimas: dict[str, datetime], ahora: datetime
) -> list[TareaProgramada]:
    """Las que nunca corrieron en este proceso, o cuyo intervalo ya paso
    desde su ultima ejecucion."""
    return [
        tarea
        for tarea in tareas
        if tarea.nombre not in ultimas or ahora - ultimas[tarea.nombre] >= tarea.intervalo
    ]


async def ejecutar_pendientes(
    tareas: list[TareaProgramada], ultimas: dict[str, datetime], ahora: datetime
) -> list[ResultadoTarea]:
    """Ejecuta cada tarea pendiente y anota su ultima ejecucion aunque
    falle: una tarea rota no se reintenta en cada vuelta del bucle (se
    reintenta en su siguiente intervalo) ni impide que corran las demas."""
    resultados: list[ResultadoTarea] = []
    for tarea in tareas_pendientes(tareas, ultimas, ahora):
        ultimas[tarea.nombre] = ahora
        try:
            await tarea.ejecutar()
        except Exception as error:  # noqa: BLE001 -- el temporizador no debe caerse
            resultados.append(ResultadoTarea(tarea.nombre, exitosa=False, error=repr(error)))
        else:
            resultados.append(ResultadoTarea(tarea.nombre, exitosa=True))
    return resultados
