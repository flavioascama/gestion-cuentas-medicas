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
"""

from __future__ import annotations

from playwright.async_api import Browser, BrowserContext, Playwright, StorageState


class GestorNavegador:
    def __init__(self, playwright: Playwright, reinicios_cada_n_trabajos: int) -> None:
        self._playwright = playwright
        self._reinicios_cada_n_trabajos = reinicios_cada_n_trabajos
        self._navegador: Browser | None = None
        self._trabajos_desde_el_ultimo_reinicio = 0

    async def _iniciar(self) -> None:
        self._navegador = await self._playwright.chromium.launch(headless=True)
        self._trabajos_desde_el_ultimo_reinicio = 0

    async def cerrar(self) -> None:
        if self._navegador is not None:
            await self._navegador.close()
            self._navegador = None

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
        return await self._navegador.new_context(storage_state=storage_state)

    async def obtener_estado_sesion(self, contexto: BrowserContext) -> StorageState:
        return await contexto.storage_state()
