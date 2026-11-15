"""Pruebas de la agenda del temporizador del sistema (CU-11, RNF-18): que
cada tarea corre al arrancar y luego solo cuando paso su intervalo, y que
una tarea que falla no detiene a las demas ni se reintenta en cada vuelta."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.infraestructura.temporizador import (
    TareaProgramada,
    ejecutar_pendientes,
    tareas_pendientes,
)

_INICIO = datetime(2026, 11, 12, 8, 0, 0, tzinfo=UTC)


def _tarea(nombre: str, intervalo: timedelta, llamadas: list[str]) -> TareaProgramada:
    async def ejecutar() -> None:
        llamadas.append(nombre)

    return TareaProgramada(nombre, intervalo, ejecutar)


async def prueba_todas_las_tareas_corren_al_arrancar() -> None:
    llamadas: list[str] = []
    tareas = [
        _tarea("vencimientos", timedelta(hours=1), llamadas),
        _tarea("cadena", timedelta(hours=24), llamadas),
    ]
    resultados = await ejecutar_pendientes(tareas, {}, _INICIO)

    assert llamadas == ["vencimientos", "cadena"]
    assert all(r.exitosa for r in resultados)


async def prueba_cada_tarea_respeta_su_intervalo() -> None:
    llamadas: list[str] = []
    tareas = [
        _tarea("vencimientos", timedelta(hours=1), llamadas),
        _tarea("cadena", timedelta(hours=24), llamadas),
    ]
    ultimas: dict[str, datetime] = {}
    await ejecutar_pendientes(tareas, ultimas, _INICIO)
    llamadas.clear()

    await ejecutar_pendientes(tareas, ultimas, _INICIO + timedelta(minutes=59))
    assert llamadas == []

    await ejecutar_pendientes(tareas, ultimas, _INICIO + timedelta(hours=1))
    assert llamadas == ["vencimientos"]

    await ejecutar_pendientes(tareas, ultimas, _INICIO + timedelta(hours=24))
    assert llamadas == ["vencimientos", "vencimientos", "cadena"]


async def prueba_una_tarea_que_falla_no_detiene_a_las_demas() -> None:
    llamadas: list[str] = []

    async def fallar() -> None:
        raise RuntimeError("base de datos caida")

    tareas = [
        TareaProgramada("rota", timedelta(hours=1), fallar),
        _tarea("sana", timedelta(hours=1), llamadas),
    ]
    ultimas: dict[str, datetime] = {}
    resultados = await ejecutar_pendientes(tareas, ultimas, _INICIO)

    assert llamadas == ["sana"]
    assert [(r.nombre, r.exitosa) for r in resultados] == [("rota", False), ("sana", True)]
    assert resultados[0].error is not None and "base de datos caida" in resultados[0].error
    # Se anota como ejecutada: no se reintenta en la vuelta siguiente,
    # sino al cumplirse su intervalo.
    assert tareas_pendientes(tareas, ultimas, _INICIO + timedelta(minutes=1)) == []
