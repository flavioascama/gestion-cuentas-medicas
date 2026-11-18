"""Ciclo de vida del navegador (Seccion 8.1): 'el trabajador mantiene una
instancia de navegador persistente y reutiliza la sesion. Un contexto o
pagina nueva por trabajo, con el estado de sesion almacenado por portal
mediante storage_state... El navegador se reinicia cada N trabajos, valor
configurable, o ante error irrecuperable'.

Crear y destruir el navegador en cada trabajo (en vez de reutilizarlo)
pondria en riesgo el umbral de 60 segundos del indicador R1.3 -- el propio
plan lo dice explicitamente, no es una micro-optimizacion propia.

Desde la Fase 15 el `storage_state` es "por portal" de verdad (antes solo
existia ACREDITA SALUD): `nuevo_contexto`/`guardar_estado_sesion` reciben
el `StorageState` ya en memoria (nunca una ruta), para que quien los llama
decida si lo cifra antes de guardarlo (Seccion 8.4, punto 4: "guarda el
estado de sesion de Playwright... cifrado") -- este modulo no sabe de
`sesion_plataforma` ni de cifrado, solo de Playwright.

Navegacion visible (2026-11-18): lo habitual es un navegador sin ventana y
a toda velocidad. Si el administrador lo pide, el navegador trabaja mas
despacio y, en el modo "ventana", se abre con su ventana en el equipo donde
corre el robot. Donde no hay pantalla (un contenedor, un servidor) la
ventana no se puede abrir: el navegador sigue sin ella y quien pidio la
tarea lo ve dentro del sistema.
"""

from __future__ import annotations

from collections.abc import Callable

import structlog
from playwright.async_api import Browser, BrowserContext, Page, Playwright, StorageState
from playwright.async_api import Error as ErrorPlaywright

registro = structlog.get_logger(__name__)


class GestorNavegador:
    def __init__(
        self,
        playwright: Playwright,
        reinicios_cada_n_trabajos: int,
        pausa_visible_ms: int = 0,
        hay_pantalla: bool = True,
    ) -> None:
        self._playwright = playwright
        self._reinicios_cada_n_trabajos = reinicios_cada_n_trabajos
        self._pausa_visible_ms = pausa_visible_ms
        # En un contenedor no hay pantalla: ni se intenta abrir la ventana.
        self._hay_pantalla = hay_pantalla
        self._navegador: Browser | None = None
        self._trabajos_desde_el_ultimo_reinicio = 0
        self._visible = False
        self._con_ventana = False
        self._muestra_ventana = False
        # Avisa de cada pagina que el robot abre (lo usa la vista en vivo).
        self.al_abrir_pagina: Callable[[Page], None] | None = None

    @property
    def muestra_ventana(self) -> bool:
        """El navegador abierto tiene su ventana en la pantalla de este equipo."""
        return self._muestra_ventana

    async def configurar(self, visible: bool, con_ventana: bool) -> None:
        """Fija como debe trabajar el navegador desde el proximo trabajo. Si
        cambia, se cierra: el siguiente contexto lo abre con el modo nuevo."""
        con_ventana = con_ventana and self._hay_pantalla
        if (visible, con_ventana) == (self._visible, self._con_ventana):
            return
        self._visible = visible
        self._con_ventana = con_ventana
        await self.cerrar()

    async def _iniciar(self) -> None:
        pausa = self._pausa_visible_ms if self._visible else 0
        self._muestra_ventana = False
        if self._con_ventana:
            try:
                self._navegador = await self._playwright.chromium.launch(
                    headless=False, slow_mo=pausa
                )
                self._muestra_ventana = True
            except ErrorPlaywright:
                registro.warning("navegador_sin_pantalla_para_la_ventana")
        if self._navegador is None:
            self._navegador = await self._playwright.chromium.launch(headless=True, slow_mo=pausa)
        self._trabajos_desde_el_ultimo_reinicio = 0

    async def cerrar(self) -> None:
        if self._navegador is not None:
            await self._navegador.close()
            self._navegador = None
        self._muestra_ventana = False

    async def reiniciar(self) -> None:
        """Seccion 8.1: 'o ante error irrecuperable' -- lo llama el robot
        cuando decide que el contexto/pagina quedaron en un estado del que
        no vale la pena intentar recuperarse."""

        await self.cerrar()
        await self._iniciar()

    async def nuevo_contexto(self, storage_state: StorageState | None = None) -> BrowserContext:
        necesita_reinicio = (
            self._navegador is None
            or self._trabajos_desde_el_ultimo_reinicio >= self._reinicios_cada_n_trabajos
        )
        if necesita_reinicio:
            await self.reiniciar()
        assert self._navegador is not None

        self._trabajos_desde_el_ultimo_reinicio += 1
        contexto = await self._navegador.new_context(storage_state=storage_state)
        if self.al_abrir_pagina is not None:
            contexto.on("page", self.al_abrir_pagina)
        return contexto

    async def obtener_estado_sesion(self, contexto: BrowserContext) -> StorageState:
        return await contexto.storage_state()
