"""AdaptadorValidadorTedefWeb: implementacion Playwright del puerto
ValidadorTedefWeb (Seccion 8.3, Fase 16).

Unica implementacion del puerto que vive en el dominio del backend
(app.dominio.integracion.puertos_validacion.ValidadorTedefWeb); corre
aqui, en el proceso trabajador (AD-02), como todos los robots. Cada
metodo publico abre y cierra su propio contexto de navegador (mismo
patron que AdaptadorAcreditacionWeb y AdaptadorSesionPlataforma) en vez
de mantener una pagina abierta entre llamadas -- por eso ningun metodo
recibe ni devuelve el id interno del lote en el simulador: las filas se
vuelven a encontrar por numero de lote + periodo cada vez (Seccion 9.2:
esos dos datos ya son columnas visibles de la tabla).

`seleccionar_perfil_y_entidad` es el gancho que
AdaptadorSesionPlataforma.iniciar_sesion (Fase 15) ejecuta despues del
CAPTCHA para esta plataforma (Seccion 9.2, punto 2: TEDEF Web exige
ademas seleccionar perfil y entidad antes de que la sesion quede activa
en el simulador) -- ver ConfiguracionPlataforma.pasos_adicionales_ingreso
en robot_sesion_plataforma.py.
"""

from __future__ import annotations

import asyncio
import io
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import openpyxl
import structlog
from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    ContextoCargaValidador,
    IdentidadLoteTedef,
    ObservacionLectura,
    ResultadoEtapaValidador,
    ValidadorTedefWeb,
)
from app.dominio.puertos_comunes import Reloj
from playwright.async_api import FilePayload, Locator, Page

from trabajador.soporte.cifrado import AlmacenSesionesCifrado
from trabajador.soporte.errores import ErrorSesionNoDisponible
from trabajador.soporte.navegador import GestorNavegador
from trabajador.soporte.pasos import RegistradorPasos
from trabajador.soporte.selectores import obtener_selector, ruta_selectores

registro = structlog.get_logger(__name__)

_PLATAFORMA = "tedef_web"
_ESTADO_OBSERVADO_DETALLADA = "OBSERVADO_DETALLADA"
_RUTA = ruta_selectores(_PLATAFORMA)


def _sel(seccion: str, clave: str) -> str:
    return obtener_selector(seccion, clave, _RUTA)


async def seleccionar_perfil_y_entidad(pagina: Page) -> None:
    """Seccion 9.2, punto 2. Siempre el perfil TEDEF-Validador-IPRESS
    (no el que el formulario marca por defecto) y la unica entidad
    disponible."""

    await pagina.check(_sel("perfil", "opcion_validador"))
    await pagina.click(_sel("perfil", "boton_seleccionar"))
    await pagina.click(_sel("entidad", "boton_seleccionar"))


class ErrorRobotValidadorTedefWeb(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ConfiguracionValidadorTedefWeb:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo
    ajustable de la Seccion 9.2, punto 4 (espera de 'Validando lote' en
    segundo plano), para no superar el limite de 5 parametros del
    constructor de AdaptadorValidadorTedefWeb."""

    url_base: str
    tiempo_limite_validacion_segundos: int
    intervalo_poll_segundos: float


class AdaptadorValidadorTedefWeb(ValidadorTedefWeb):
    def __init__(
        self,
        gestor_navegador: GestorNavegador,
        almacen_sesiones: AlmacenSesionesCifrado,
        configuracion: ConfiguracionValidadorTedefWeb,
        reloj: Reloj,
        pasos: RegistradorPasos | None = None,
    ) -> None:
        self._pasos = pasos
        self._gestor_navegador = gestor_navegador
        self._almacen_sesiones = almacen_sesiones
        self._url_base = configuracion.url_base
        self._reloj = reloj
        self._tiempo_limite_validacion_segundos = configuracion.tiempo_limite_validacion_segundos
        self._intervalo_poll_segundos = configuracion.intervalo_poll_segundos

    async def _paso(self, pagina: Page, descripcion: str) -> None:
        if self._pasos is not None:
            await self._pasos.anotar(pagina, _PLATAFORMA, descripcion)

    @asynccontextmanager
    async def _pagina_autenticada(self) -> AsyncIterator[Page]:
        estado_sesion = self._almacen_sesiones.cargar(_PLATAFORMA)
        if estado_sesion is None:
            raise ErrorSesionNoDisponible("No hay una sesion asistida guardada para TEDEF Web.")

        contexto = await self._gestor_navegador.nuevo_contexto(estado_sesion)
        pagina = await contexto.new_page()
        try:
            await pagina.goto(f"{self._url_base}{_sel('lotes_por_validar', 'ruta')}")
            if pagina.url.endswith("/ingreso"):
                raise ErrorSesionNoDisponible(
                    "La sesion asistida guardada de TEDEF Web ya no es valida."
                )
            await self._paso(pagina, "Lotes por validar, con la sesión iniciada")
            yield pagina
        except ErrorSesionNoDisponible:
            raise
        except Exception:
            registro.warning("robot_validador_tedef_web_error")
            await self._gestor_navegador.reiniciar()
            raise
        finally:
            await contexto.close()

    async def cargar_lote(self, contexto: ContextoCargaValidador) -> ResultadoEtapaValidador:
        async with self._pagina_autenticada() as pagina:
            await pagina.goto(f"{self._url_base}{_sel('lotes_por_validar', 'ruta_nuevo')}")
            archivos: list[FilePayload] = [
                {"name": a.nombre, "mimeType": "text/plain", "buffer": a.contenido}
                for a in contexto.archivos
            ]
            campo = pagina.locator(_sel("lotes_por_validar", "campo_archivos"))
            await campo.set_input_files(archivos)
            await self._paso(pagina, "Archivos del lote cargados en el formulario")
            await pagina.click(_sel("lotes_por_validar", "boton_registrar_archivos"))
            await self._paso(pagina, "Resultado del registro del lote")
            return await self._leer_resultado_registro(pagina)

    async def _leer_resultado_registro(self, pagina: Page) -> ResultadoEtapaValidador:
        conforme = pagina.locator(_sel("lotes_por_validar", "resultado_conforme"))
        if await conforme.count() > 0:
            return ResultadoEtapaValidador(
                conforme=True, estado_informado="Registrado, Errores: Ninguno"
            )

        observado = pagina.locator(_sel("lotes_por_validar", "resultado_observado"))
        texto = await _texto(observado)
        enlace = pagina.locator(_sel("lotes_por_validar", "descargar_observaciones"))
        reporte = await self._descargar(pagina, enlace) if await enlace.count() > 0 else None
        observaciones = _parsear_reporte_forma(reporte.contenido) if reporte is not None else ()
        return ResultadoEtapaValidador(
            conforme=False, estado_informado=texto, observaciones=observaciones, reporte=reporte
        )

    async def validar_lote(self, identidad: IdentidadLoteTedef) -> ResultadoEtapaValidador:
        async with self._pagina_autenticada() as pagina:
            fila = await self._fila_o_error(pagina, "lotes_por_validar", identidad)
            await fila.locator(_sel("lotes_por_validar", "checkbox_lote")).check()
            await self._paso(pagina, "Lote marcado para validar")
            await pagina.click(_sel("lotes_por_validar", "boton_validar_lotes"))
            resultado = await self._esperar_resolucion(pagina, identidad)
            await self._paso(pagina, "Resultado de la validación del lote")
            return resultado

    async def _esperar_resolucion(
        self, pagina: Page, identidad: IdentidadLoteTedef
    ) -> ResultadoEtapaValidador:
        """Seccion 9.2, punto 4: 'Validando lote' en segundo plano;
        refresca la tabla hasta que resuelve. Si el lote desaparece de
        'Lotes por Validar' paso a 'Lotes por Enviar' (VALIDADO); si
        queda con estado OBSERVADO_DETALLADA, descarga el reporte."""

        limite = self._reloj.ahora() + timedelta(seconds=self._tiempo_limite_validacion_segundos)
        while self._reloj.ahora() < limite:
            await pagina.goto(f"{self._url_base}{_sel('lotes_por_validar', 'ruta')}")
            fila = await self._fila_opcional(pagina, "lotes_por_validar", identidad)
            if fila is None:
                return ResultadoEtapaValidador(conforme=True, estado_informado="VALIDADO")

            estado = await _texto(fila.locator(_sel("lotes_por_validar", "estado_lote")))
            if estado == _ESTADO_OBSERVADO_DETALLADA:
                enlace = fila.locator(_sel("lotes_por_validar", "descargar_error_validacion"))
                reporte = await self._descargar(pagina, enlace)
                return ResultadoEtapaValidador(
                    conforme=False,
                    estado_informado=estado,
                    observaciones=_parsear_reporte_detallada(reporte.contenido),
                    reporte=reporte,
                )
            await asyncio.sleep(self._intervalo_poll_segundos)

        raise ErrorRobotValidadorTedefWeb(
            f"Se agoto el tiempo limite esperando la validacion detallada del lote "
            f"{identidad.numero}/{identidad.periodo}."
        )

    async def descargar_archivo_transmision(self, identidad: IdentidadLoteTedef) -> ArchivoLote:
        async with self._pagina_autenticada() as pagina:
            await pagina.goto(f"{self._url_base}{_sel('lotes_por_enviar', 'ruta')}")
            fila = await self._fila_o_error(pagina, "lotes_por_enviar", identidad)
            enlace = fila.locator(_sel("lotes_por_enviar", "descargar_s01"))
            await self._paso(pagina, "Lotes por enviar: archivo de transmisión")
            return await self._descargar(pagina, enlace)

    async def enviar_a_susalud(self, lotes: tuple[IdentidadLoteTedef, ...]) -> None:
        async with self._pagina_autenticada() as pagina:
            await pagina.goto(f"{self._url_base}{_sel('lotes_por_enviar', 'ruta')}")
            for identidad in lotes:
                fila = await self._fila_o_error(pagina, "lotes_por_enviar", identidad)
                await fila.locator(_sel("lotes_por_enviar", "checkbox_lote")).check()
            await self._paso(pagina, "Lotes marcados para enviar a SUSALUD")
            await pagina.click(_sel("lotes_por_enviar", "boton_enviar_lotes"))
            await self._paso(pagina, "Envío a SUSALUD realizado")

    async def _fila_opcional(
        self, pagina: Page, seccion: str, identidad: IdentidadLoteTedef
    ) -> Locator | None:
        numero, periodo = re.escape(identidad.numero), re.escape(identidad.periodo)
        # re.DOTALL: el texto de la fila trae saltos de linea reales entre
        # celdas (espacios en blanco del propio HTML renderizado, Seccion
        # 9.2), y sin el "." de los lookahead no cruza esa linea -- ningun
        # patron calzaba nunca sin este flag (bug real encontrado en la
        # verificacion E2E de esta fase, ver docs/DECISIONES.md).
        patron = re.compile(rf"(?=.*{numero})(?=.*{periodo})", re.DOTALL)
        filas = pagina.locator(_sel(seccion, "fila_lote")).filter(has_text=patron)
        if await filas.count() == 0:
            return None
        return filas.first

    async def _fila_o_error(
        self, pagina: Page, seccion: str, identidad: IdentidadLoteTedef
    ) -> Locator:
        fila = await self._fila_opcional(pagina, seccion, identidad)
        if fila is None:
            raise ErrorRobotValidadorTedefWeb(
                f"No se encontro el lote {identidad.numero}/{identidad.periodo} en {seccion}."
            )
        return fila

    async def _descargar(self, pagina: Page, enlace: Locator) -> ArchivoLote:
        href = await enlace.get_attribute("href")
        if href is None:
            raise ErrorRobotValidadorTedefWeb("El enlace de descarga no tiene href.")
        url = href if href.startswith("http") else f"{self._url_base}{href}"
        respuesta = await pagina.context.request.get(url)
        contenido = await respuesta.body()
        nombre = _nombre_adjunto(respuesta.headers.get("content-disposition"))
        return ArchivoLote(nombre=nombre or href.rsplit("/", 1)[-1], contenido=contenido)


async def _texto(locador: Locator) -> str:
    texto = await locador.text_content()
    return (texto or "").strip()


def _nombre_adjunto(encabezado: str | None) -> str | None:
    if not encabezado:
        return None
    coincidencia = re.search(r'filename="([^"]+)"', encabezado)
    return coincidencia.group(1) if coincidencia else None


def _filas_de_datos(contenido: bytes, primera_columna_encabezado: str) -> list[tuple[Any, ...]]:
    """Reportes .xlsx del validador (Seccion 9.2): siete filas de
    encabezado de texto libre (IPRESS, IAFAS, lote, usuario, perfil,
    aviso SIM-*, linea en blanco -- ver app/reportes.py del simulador)
    antes de la fila con los nombres de columna. Se busca esa fila por
    contenido en vez de por numero fijo, para no depender de que el
    simulador nunca cambie cuantas lineas de encabezado escribe."""

    libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    hoja = libro.active
    assert hoja is not None
    filas = list(hoja.iter_rows(values_only=True))
    for indice, fila in enumerate(filas):
        if fila and fila[0] == primera_columna_encabezado:
            return [f for f in filas[indice + 1 :] if f and f[0] is not None]
    return []


def _parsear_reporte_forma(contenido: bytes) -> tuple[ObservacionLectura, ...]:
    filas = _filas_de_datos(contenido, "Tabla")
    return tuple(
        ObservacionLectura(
            tabla=None if fila[0] in (None, "-") else str(fila[0]),
            numero_linea=None,
            campo_clave=None,
            campo=None,
            valor_observado=None,
            codigo_error=str(fila[1]),
            descripcion=str(fila[2]),
        )
        for fila in filas
    )


def _parsear_reporte_detallada(contenido: bytes) -> tuple[ObservacionLectura, ...]:
    filas = _filas_de_datos(contenido, "IPRESS/IAFAS")
    return tuple(
        ObservacionLectura(
            tabla=_texto_celda(fila[2]),
            numero_linea=int(fila[3]) if fila[3] is not None else None,
            campo_clave=_texto_celda(fila[4]),
            campo=_texto_celda(fila[5]),
            valor_observado=_texto_celda(fila[6]),
            codigo_error=str(fila[7]),
            descripcion=str(fila[8]),
        )
        for fila in filas
    )


def _texto_celda(valor: Any) -> str | None:
    return None if valor is None else str(valor)
