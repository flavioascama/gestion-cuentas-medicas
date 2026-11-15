"""Pruebas de GestorNavegador (Seccion 8.1) con un Playwright falso -- sin
lanzar un navegador real: verifican la logica de reutilizacion y de
reinicio cada N trabajos, que es la parte no trivial, no el
`chromium.launch` en si.

Desde la Fase 15, `storage_state` viaja en memoria (un dict, nunca una
ruta): el cifrado por portal lo maneja quien llama
(trabajador.soporte.cifrado.AlmacenSesionesCifrado), no este modulo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trabajador.soporte.navegador import GestorNavegador


@dataclass
class _ContextoFalso:
    cerrado: bool = False
    estado_devuelto: dict[str, Any] = field(default_factory=dict)

    async def storage_state(self) -> dict[str, Any]:
        return self.estado_devuelto


@dataclass
class _NavegadorFalso:
    contextos_creados: list[dict[str, object] | None] = field(default_factory=list)
    cerrado: bool = False

    async def new_context(self, storage_state: dict[str, Any] | None = None) -> _ContextoFalso:
        self.contextos_creados.append(storage_state)
        return _ContextoFalso()

    async def close(self) -> None:
        self.cerrado = True


@dataclass
class _ChromiumFalso:
    navegadores_lanzados: list[_NavegadorFalso] = field(default_factory=list)

    async def launch(self, headless: bool = True) -> _NavegadorFalso:
        navegador = _NavegadorFalso()
        self.navegadores_lanzados.append(navegador)
        return navegador


@dataclass
class _PlaywrightFalso:
    chromium: _ChromiumFalso = field(default_factory=_ChromiumFalso)


async def prueba_primer_contexto_lanza_el_navegador() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]

    await gestor.nuevo_contexto()

    assert len(playwright_falso.chromium.navegadores_lanzados) == 1


async def prueba_reutiliza_el_mismo_navegador_para_varios_trabajos() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]

    for _ in range(5):
        await gestor.nuevo_contexto()

    assert len(playwright_falso.chromium.navegadores_lanzados) == 1


async def prueba_reinicia_el_navegador_cada_n_trabajos() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=3)  # type: ignore[arg-type]

    for _ in range(7):  # 3 + 3 + 1 -> tres navegadores distintos
        await gestor.nuevo_contexto()

    assert len(playwright_falso.chromium.navegadores_lanzados) == 3
    assert playwright_falso.chromium.navegadores_lanzados[0].cerrado
    assert playwright_falso.chromium.navegadores_lanzados[1].cerrado
    assert not playwright_falso.chromium.navegadores_lanzados[2].cerrado


async def prueba_reiniciar_cierra_el_navegador_actual() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]
    await gestor.nuevo_contexto()
    navegador_original = playwright_falso.chromium.navegadores_lanzados[0]

    await gestor.reiniciar()

    assert navegador_original.cerrado
    assert len(playwright_falso.chromium.navegadores_lanzados) == 2


async def prueba_sin_storage_state_pasa_none_a_new_context() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]

    await gestor.nuevo_contexto()

    navegador = playwright_falso.chromium.navegadores_lanzados[0]
    assert navegador.contextos_creados[0] is None


async def prueba_pasa_el_storage_state_recibido_a_new_context() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]
    estado = {"cookies": [{"name": "sesion", "value": "abc"}]}

    await gestor.nuevo_contexto(estado)

    navegador = playwright_falso.chromium.navegadores_lanzados[0]
    assert navegador.contextos_creados[0] == estado


async def prueba_obtener_estado_sesion_devuelve_lo_que_da_playwright() -> None:
    playwright_falso = _PlaywrightFalso()
    gestor = GestorNavegador(playwright_falso, reinicios_cada_n_trabajos=20)  # type: ignore[arg-type]
    contexto = await gestor.nuevo_contexto()
    contexto.estado_devuelto = {"cookies": [{"name": "sesion", "value": "xyz"}]}  # type: ignore[attr-defined]

    estado = await gestor.obtener_estado_sesion(contexto)  # type: ignore[arg-type]

    assert estado == {"cookies": [{"name": "sesion", "value": "xyz"}]}
