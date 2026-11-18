"""AdaptadorSesionPlataforma: implementacion Playwright del puerto
AsistenteSesionPlataforma (Seccion 8.4, puntos 2 a 5).

Unica implementacion del puerto que vive en el dominio del backend
(app.dominio.plataformas.puertos.AsistenteSesionPlataforma); corre aqui,
en el proceso trabajador (AD-02), porque es la unica pieza del sistema
que importa Playwright. A diferencia de AdaptadorAcreditacionWeb, este
adaptador SI necesita leer y escribir `sesion_plataforma` mientras la
pagina de ingreso sigue abierta y esperando la respuesta humana
(registrar la imagen, sondear hasta que llegue la respuesta) -- algo que
no encaja en la forma de "un puerto, un resultado" del resto de los
robots. Recibe una fabrica de sesiones SQLAlchemy (no un repositorio ya
construido) para abrir una conexion nueva y corta en cada paso, en vez de
mantener una sola conexion abierta durante los hasta 120 segundos de
espera de cada intento de CAPTCHA."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import structlog
from app.dominio.plataformas.puertos import AsistenteSesionPlataforma, ErrorSesionFallida
from app.dominio.plataformas.valores import SesionPlataforma
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)
from playwright.async_api import Page
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trabajador.soporte.cifrado import AlmacenSesionesCifrado
from trabajador.soporte.navegador import GestorNavegador
from trabajador.soporte.pasos import RegistradorPasos
from trabajador.soporte.selectores import (
    ErrorSelectorNoEncontrado,
    obtener_selector,
    ruta_selectores,
)

registro = structlog.get_logger(__name__)

PasosAdicionalesIngreso = Callable[[Page], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ConfiguracionPlataforma:
    url_base: str
    usuario: str
    clave: str
    # Seccion 9.2 (Fase 16): TEDEF Web exige, ademas de usuario/clave y
    # CAPTCHA, seleccionar un perfil y una entidad antes de que la sesion
    # quede realmente activa en el servidor del simulador -- pasos que no
    # forman parte del protocolo generico de la Seccion 8.4. En vez de
    # ensuciar este modulo generico con vocabulario de una plataforma en
    # particular, cada ConfiguracionPlataforma puede declarar un gancho
    # opcional que se ejecuta despues del CAPTCHA y antes de guardar el
    # storage_state. None (el caso de ACREDITA SALUD) no cambia nada.
    pasos_adicionales_ingreso: PasosAdicionalesIngreso | None = None


@dataclass(frozen=True, slots=True)
class ConfiguracionAsistente:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa
    todo lo ajustable por plataforma y por Seccion 8.4 en un solo lugar,
    para no superar el limite de 5 parametros en el constructor."""

    plataformas: dict[str, ConfiguracionPlataforma]
    tiempo_limite_captcha_segundos: int
    intervalo_poll_segundos: float
    duracion_sesion_minutos: int
    max_intentos_captcha: int


class AdaptadorSesionPlataforma(AsistenteSesionPlataforma):
    def __init__(
        self,
        gestor_navegador: GestorNavegador,
        almacen_sesiones: AlmacenSesionesCifrado,
        fabrica_sesiones: async_sessionmaker[AsyncSession],
        reloj: Reloj,
        configuracion: ConfiguracionAsistente,
    ) -> None:
        self._pasos: RegistradorPasos | None = None
        self._gestor_navegador = gestor_navegador
        self._almacen_sesiones = almacen_sesiones
        self._fabrica_sesiones = fabrica_sesiones
        self._reloj = reloj
        self._configuracion = configuracion

    @asynccontextmanager
    async def _repositorio(self) -> AsyncIterator[RepositorioSesionPlataformaSql]:
        """Conexion nueva y corta por paso (ver docstring del modulo): no
        se mantiene una sola sesion de SQLAlchemy abierta durante los
        hasta 120 segundos de espera de cada intento de CAPTCHA."""

        async with self._fabrica_sesiones() as sesion:
            yield RepositorioSesionPlataformaSql(sesion)

    async def _obtener(self, sesion_id: int) -> SesionPlataforma | None:
        async with self._repositorio() as repositorio:
            return await repositorio.obtener(sesion_id)

    async def iniciar_sesion(self, sesion_id: int, plataforma: str) -> None:
        config = self._configuracion.plataformas.get(plataforma)
        if config is None:
            raise ErrorSesionFallida(
                f"No hay configuracion de robot para la plataforma {plataforma!r} todavia."
            )
        ruta = ruta_selectores(plataforma)

        contexto = await self._gestor_navegador.nuevo_contexto()
        pagina = await contexto.new_page()
        try:
            await self._ingresar_credenciales(pagina, ruta, config)
            # La clave se ve como puntos: es un campo de contrasena.
            await self._paso(pagina, plataforma, "Pantalla de ingreso de la plataforma")
            await self._resolver_captcha(pagina, ruta, sesion_id, config)
            if config.pasos_adicionales_ingreso is not None:
                await config.pasos_adicionales_ingreso(pagina)
            await self._paso(pagina, plataforma, "Ingreso aceptado por la plataforma")
            estado = await self._gestor_navegador.obtener_estado_sesion(contexto)
            self._almacen_sesiones.guardar(plataforma, estado)
            expira_en = self._reloj.ahora() + timedelta(
                minutes=self._configuracion.duracion_sesion_minutos
            )
            async with self._repositorio() as repositorio:
                await repositorio.activar(sesion_id, expira_en)
        except ErrorSesionFallida:
            registro.warning(
                "sesion_plataforma_fallida", sesion_id=sesion_id, plataforma=plataforma
            )
            raise
        except Exception:
            registro.warning(
                "robot_sesion_plataforma_error", sesion_id=sesion_id, plataforma=plataforma
            )
            await self._gestor_navegador.reiniciar()
            raise
        finally:
            await contexto.close()

    def con_pasos(self, pasos: RegistradorPasos) -> AdaptadorSesionPlataforma:
        """Aparte del constructor, que ya recibe cinco colaboradores."""
        self._pasos = pasos
        return self

    async def _paso(self, pagina: Page, plataforma: str, descripcion: str) -> None:
        if self._pasos is not None:
            await self._pasos.anotar(pagina, plataforma, descripcion)

    async def _ingresar_credenciales(
        self, pagina: Page, ruta: Path, config: ConfiguracionPlataforma
    ) -> None:
        await pagina.goto(f"{config.url_base}/ingreso")
        await pagina.fill(obtener_selector("ingreso", "campo_usuario", ruta), config.usuario)
        await pagina.fill(obtener_selector("ingreso", "campo_clave", ruta), config.clave)

    async def _resolver_captcha(
        self, pagina: Page, ruta: Path, sesion_id: int, config: ConfiguracionPlataforma
    ) -> None:
        """Seccion 8.4, puntos 2 a 5: publica la imagen, espera la
        respuesta humana con tiempo limite, la envia y reintenta hasta
        `max_intentos_captcha` veces si estaba equivocada."""

        for intento in range(self._configuracion.max_intentos_captcha):
            imagen = await pagina.locator(
                obtener_selector("ingreso", "imagen_captcha", ruta)
            ).screenshot()
            async with self._repositorio() as repositorio:
                if intento == 0:
                    await repositorio.registrar_captcha(sesion_id, imagen)
                else:
                    await repositorio.reintentar_captcha(sesion_id, imagen)

            respuesta = await self._esperar_respuesta_humana(sesion_id)
            if respuesta is None:
                mensaje = "Se agoto el tiempo limite esperando la respuesta del CAPTCHA."
                async with self._repositorio() as repositorio:
                    await repositorio.marcar_fallida(sesion_id, mensaje)
                raise ErrorSesionFallida(mensaje)

            if await self._enviar_y_verificar(pagina, ruta, respuesta, config):
                return

        mensaje = f"Se agotaron los {self._configuracion.max_intentos_captcha} intentos de CAPTCHA."
        async with self._repositorio() as repositorio:
            await repositorio.marcar_fallida(sesion_id, mensaje)
        raise ErrorSesionFallida(mensaje)

    async def _esperar_respuesta_humana(self, sesion_id: int) -> str | None:
        """None si se agota `tiempo_limite_captcha_segundos` sin que la
        sesion pase a CAPTCHA_RESPONDIDO (Seccion 8.4, punto 4)."""

        limite = self._reloj.ahora() + timedelta(
            seconds=self._configuracion.tiempo_limite_captcha_segundos
        )
        while self._reloj.ahora() < limite:
            sesion = await self._obtener(sesion_id)
            if (
                sesion is not None
                and sesion.estado == "CAPTCHA_RESPONDIDO"
                and sesion.respuesta_captcha
            ):
                return sesion.respuesta_captcha
            await asyncio.sleep(self._configuracion.intervalo_poll_segundos)
        return None

    async def _enviar_y_verificar(
        self, pagina: Page, ruta: Path, respuesta: str, config: ConfiguracionPlataforma
    ) -> bool:
        """True si el ingreso tuvo exito. Lanza ErrorSesionFallida si el
        usuario o la clave configurados son invalidos (no tiene sentido
        reintentar el CAPTCHA para eso). False si el CAPTCHA estaba
        equivocado, para que quien llama reintente con una imagen nueva.

        Rellena usuario y clave en cada llamada, no solo en la primera
        (Fase 20, bug encontrado al verificar contra el simulador real):
        "Refrescar Imagen" (Seccion 9.1) es un enlace que recarga toda la
        pagina de /ingreso, vaciando el formulario completo, no solo la
        imagen. Ambos campos son `required` en el HTML; si quedan vacios,
        el navegador bloquea el envio del formulario ANTES de llegar al
        servidor (ninguna peticion POST sale), asi que ningun
        `data-testid="error-*"` aparece nunca -- y la ausencia de
        cualquier error se leia, incorrectamente, como exito."""

        await pagina.fill(obtener_selector("ingreso", "campo_usuario", ruta), config.usuario)
        await pagina.fill(obtener_selector("ingreso", "campo_clave", ruta), config.clave)
        await pagina.fill(obtener_selector("ingreso", "campo_captcha", ruta), respuesta)
        await pagina.click(obtener_selector("ingreso", "boton_ingresar", ruta))

        if await self._hay_error(pagina, ruta, "error_usuario") or await self._hay_error(
            pagina, ruta, "error_clave"
        ):
            raise ErrorSesionFallida(
                "Usuario o contrasena de la plataforma invalidos (revisar variables de entorno)."
            )
        if await self._hay_error(pagina, ruta, "error_captcha"):
            await pagina.click(obtener_selector("ingreso", "boton_refrescar_captcha", ruta))
            return False
        return True

    async def _hay_error(self, pagina: Page, ruta: Path, clave_selector: str) -> bool:
        try:
            selector = obtener_selector("ingreso", clave_selector, ruta)
        except ErrorSelectorNoEncontrado:
            # No toda plataforma distingue estas causas de error (Seccion
            # 9.2: TEDEF Web solo tiene un mensaje combinado para
            # usuario/clave, a diferencia de ACREDITA SALUD). Una clave
            # de selector ausente en el YAML de esa plataforma significa
            # "no expone esa distincion", no un error de configuracion.
            return False
        return await pagina.locator(selector).count() > 0
