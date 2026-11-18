"""Navegacion visible del robot (2026-11-17 y 2026-11-18).

Con la opcion apagada, que es lo habitual, esto no hace nada. Si el
administrador la activo, en cada trabajo:

- el navegador trabaja mas despacio y, en el modo "ventana", con su ventana
  abierta en este equipo (lo decide `GestorNavegador`);
- cada paso queda anotado (que hizo, donde y cuando), sin imagen: es el
  registro que consulta el administrador;
- si el navegador no tiene ventana, lo que muestra se publica cada fraccion
  de segundo para que quien pidio la tarea lo vea en vivo dentro del
  sistema. Es un solo cuadro por trabajo, cifrado (C-05, C-12), que se borra
  al terminar.

Nada de esto puede hacer fallar al robot ni demorarlo: si la base o la
pagina no responden, el paso o el cuadro se omiten y queda un aviso en el
registro.

Dos cuidados que salieron de las pruebas de integracion (2026-11-18):
- El cuadro en vivo llega por la transmision de pantalla del navegador
  (`Page.startScreencast`), no con capturas de la pagina: una captura
  propia chocaba con la que el robot toma de la imagen del codigo de
  verificacion y lo dejaba esperando.
- La publicacion nunca se cancela a mitad de una escritura (dejaria una
  transaccion abierta que bloquea al trabajo siguiente): al terminar se le
  avisa y se espera a que acabe su vuelta."""

from __future__ import annotations

import asyncio
import base64
from typing import Any

import structlog
from app.dominio.plataformas.navegacion_robot import (
    MODO_VENTANA,
    CuadroEnVivo,
    PasoRegistrado,
    limite_de_retencion,
    url_sin_consulta,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)
from playwright.async_api import CDPSession, Page
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trabajador.soporte.navegador import GestorNavegador

registro = structlog.get_logger(__name__)

# Suficiente para leer la pantalla; cada cuadro pesa decenas de KB.
_TRANSMISION = {"format": "jpeg", "quality": 55, "maxWidth": 1280, "maxHeight": 720}


class _Pantalla:
    """Lo ultimo que el navegador transmitio de una pagina."""

    def __init__(self) -> None:
        self.imagen: bytes | None = None

    async def encender(self, pagina: Page) -> None:
        canal = await pagina.context.new_cdp_session(pagina)
        canal.on("Page.screencastFrame", lambda cuadro: self._recibir(canal, cuadro))
        await canal.send("Page.startScreencast", _TRANSMISION)

    def _recibir(self, canal: CDPSession, cuadro: dict[str, Any]) -> None:
        self.imagen = base64.b64decode(cuadro["data"])
        # El navegador solo manda el siguiente cuadro si se le confirma este.
        confirmacion = asyncio.ensure_future(
            canal.send("Page.screencastFrameAck", {"sessionId": cuadro["sessionId"]})
        )
        confirmacion.add_done_callback(lambda tarea: tarea.cancelled() or tarea.exception())


class RegistradorPasos:
    def __init__(
        self,
        fabrica_sesiones: async_sessionmaker[AsyncSession],
        reloj: Reloj,
        navegador: GestorNavegador,
        intervalo_cuadro_segundos: float = 0.35,
        pausa_paso_segundos: float = 1.0,
    ) -> None:
        self._fabrica_sesiones = fabrica_sesiones
        self._reloj = reloj
        self._navegador = navegador
        self._intervalo = intervalo_cuadro_segundos
        self._pausa_paso = pausa_paso_segundos
        # El trabajador atiende un trabajo a la vez: basta con recordar cual.
        self._trabajo_id: int | None = None
        self._transmisiones: list[asyncio.Task[None]] = []
        self._publico = False
        navegador.al_abrir_pagina = self.observar

    async def iniciar(self, trabajo_id: int) -> None:
        """Al tomar un trabajo: lee la opcion del administrador, deja el
        navegador en ese modo y borra lo que ya cumplio su retencion."""
        self._trabajo_id = None
        self._publico = False
        activa, con_ventana = False, False
        try:
            async with self._fabrica_sesiones() as sesion:
                repositorio = RepositorioNavegacionRobotSql(sesion)
                opcion = await repositorio.opcion_navegacion()
                activa, con_ventana = opcion.activa, opcion.modo == MODO_VENTANA
                await repositorio.borrar_cuadros()
                if activa:
                    await repositorio.purgar_anteriores_a(limite_de_retencion(self._reloj))
                await sesion.commit()
            await self._navegador.configurar(visible=activa, con_ventana=activa and con_ventana)
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning("navegacion_robot_no_disponible", trabajo_id=trabajo_id)
            return
        if activa:
            self._trabajo_id = trabajo_id

    async def terminar(self) -> None:
        """Al soltar el trabajo: deja de publicar y borra el cuadro en vivo."""
        self._trabajo_id = None
        transmisiones, self._transmisiones = self._transmisiones, []
        # Sin trabajo en curso, cada transmision termina sola en su vuelta.
        await asyncio.gather(*transmisiones, return_exceptions=True)
        if not self._publico:
            return
        self._publico = False
        try:
            # Da tiempo a que quien mira reciba el ultimo cuadro publicado.
            await asyncio.sleep(self._pausa_paso)
            async with self._fabrica_sesiones() as sesion:
                await RepositorioNavegacionRobotSql(sesion).borrar_cuadros()
                await sesion.commit()
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning("cuadro_robot_no_borrado")

    def observar(self, pagina: Page) -> None:
        """El robot abrio una pagina: si no tiene ventana, se publica en vivo."""
        if self._trabajo_id is None or self._navegador.muestra_ventana:
            return
        tarea = asyncio.get_running_loop().create_task(self._transmitir(pagina, self._trabajo_id))
        self._transmisiones.append(tarea)

    async def _transmitir(self, pagina: Page, trabajo_id: int) -> None:
        pantalla = _Pantalla()
        try:
            await pantalla.encender(pagina)
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning("robot_en_vivo_no_disponible", trabajo_id=trabajo_id)
            return
        while self._trabajo_id == trabajo_id and not pagina.is_closed():
            if pantalla.imagen is not None:
                await self._publicar(trabajo_id, pagina.url, pantalla.imagen)
            await asyncio.sleep(self._intervalo)

    async def _publicar(self, trabajo_id: int, url: str, imagen: bytes) -> None:
        cuadro = CuadroEnVivo(
            trabajo_id=trabajo_id,
            url=url_sin_consulta(url),
            imagen=imagen,
            instante=self._reloj.ahora(),
        )
        try:
            async with self._fabrica_sesiones() as sesion:
                await RepositorioNavegacionRobotSql(sesion).guardar_cuadro(cuadro)
                await sesion.commit()
            self._publico = True
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.debug("cuadro_robot_no_publicado", trabajo_id=trabajo_id)

    async def anotar(self, pagina: Page, plataforma: str, descripcion: str) -> None:
        """Deja el paso en el registro y lo sostiene un momento en pantalla."""
        if self._trabajo_id is None:
            return
        trabajo_id = self._trabajo_id
        try:
            paso = PasoRegistrado(
                trabajo_id=trabajo_id,
                plataforma=plataforma,
                descripcion=descripcion,
                url=url_sin_consulta(pagina.url),
            )
            async with self._fabrica_sesiones() as sesion:
                await RepositorioNavegacionRobotSql(sesion).registrar_paso(paso)
                await sesion.commit()
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning("paso_robot_no_anotado", trabajo_id=trabajo_id, paso=descripcion)
        await asyncio.sleep(self._pausa_paso)
