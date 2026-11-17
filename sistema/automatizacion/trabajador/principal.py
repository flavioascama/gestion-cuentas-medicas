"""Proceso trabajador (AD-02): consume la cola `trabajo` con
`SELECT ... FOR UPDATE SKIP LOCKED` (AD-03) y ejecuta el robot que
corresponda.

Uso:
    uv run python -m trabajador.principal              # bucle infinito
    uv run python -m trabajador.principal --una-vez     # un solo trabajo, para verificacion manual
"""

from __future__ import annotations

import argparse
import asyncio

import structlog
from app.dominio.acreditacion.casos_uso import TIPO_TRABAJO_CONSULTAR_COBERTURA
from app.dominio.comunicaciones.casos_uso import (
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
)
from app.dominio.integracion.casos_uso import TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS
from app.dominio.integracion.casos_uso_validacion import (
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
    TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD,
)
from app.dominio.plataformas.casos_uso import TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.comunicaciones.fuentes import FuenteCorreoImap, FuentePortalIafas
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.transmision.consultor_respuesta_receptor_http import (
    ConsultorRespuestaReceptorHttp,
)
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trabajador.configuracion import configuracion
from trabajador.manejadores import MANEJADORES, Adaptadores, manejar_error
from trabajador.manejadores_comunicaciones import FuentesComunicaciones
from trabajador.robots.robot_acreditacion import AdaptadorAcreditacionWeb
from trabajador.robots.robot_sesion_plataforma import (
    AdaptadorSesionPlataforma,
    ConfiguracionAsistente,
    ConfiguracionPlataforma,
)
from trabajador.robots.robot_validador_tedef_web import (
    AdaptadorValidadorTedefWeb,
    ConfiguracionValidadorTedefWeb,
    seleccionar_perfil_y_entidad,
)
from trabajador.soporte.cifrado import AlmacenSesionesCifrado
from trabajador.soporte.evidencias import AlmacenEvidenciasCifrado
from trabajador.soporte.navegador import GestorNavegador
from trabajador.soporte.pasos import RegistradorPasos

registro = structlog.get_logger(__name__)

_TIPOS_ATENDIDOS = (
    TIPO_TRABAJO_CONSULTAR_COBERTURA,
    TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
    TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA,
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
    TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD,
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
)


async def _ciclo(
    fabrica_sesiones: async_sessionmaker[AsyncSession], adaptadores: Adaptadores
) -> bool:
    """Devuelve True si tomo y proceso un trabajo (exitoso o no); False si
    no habia ninguno pendiente."""

    async with fabrica_sesiones() as sesion:
        trabajo = await RepositorioTrabajosSql(sesion).tomar_siguiente(_TIPOS_ATENDIDOS)
    if trabajo is None:
        return False

    if adaptadores.pasos is not None:
        await adaptadores.pasos.iniciar(trabajo.id)
    try:
        await MANEJADORES[trabajo.tipo](fabrica_sesiones, adaptadores, trabajo)
    except Exception as error:  # noqa: BLE001 -- cualquier fallo del robot debe reintentarse
        await manejar_error(fabrica_sesiones, trabajo, error)
    finally:
        if adaptadores.pasos is not None:
            adaptadores.pasos.terminar()
    return True


def _construir_configuracion_asistente() -> ConfiguracionAsistente:
    return ConfiguracionAsistente(
        plataformas={
            "acredita_salud": ConfiguracionPlataforma(
                url_base=configuracion.acredita_salud_url_base,
                usuario=configuracion.acredita_salud_usuario,
                clave=configuracion.acredita_salud_clave,
            ),
            "tedef_web": ConfiguracionPlataforma(
                url_base=configuracion.tedef_web_url_base,
                usuario=configuracion.tedef_web_usuario,
                clave=configuracion.tedef_web_clave,
                pasos_adicionales_ingreso=seleccionar_perfil_y_entidad,
            ),
        },
        tiempo_limite_captcha_segundos=configuracion.tiempo_limite_captcha_segundos,
        intervalo_poll_segundos=configuracion.intervalo_poll_captcha_segundos,
        duracion_sesion_minutos=configuracion.duracion_sesion_plataforma_minutos,
        max_intentos_captcha=configuracion.max_intentos_captcha,
    )


def _construir_fuentes_comunicaciones() -> FuentesComunicaciones:
    correo = None
    if configuracion.correo_imap_host:
        correo = FuenteCorreoImap(
            configuracion.correo_imap_host,
            configuracion.correo_imap_puerto,
            configuracion.correo_imap_usuario,
            configuracion.correo_imap_clave,
            configuracion.correo_imap_tls,
        )
    return FuentesComunicaciones(
        portal=FuentePortalIafas(configuracion.receptor_iafas_url_base), correo=correo
    )


def _construir_adaptadores(
    gestor_navegador: GestorNavegador,
    almacen_sesiones: AlmacenSesionesCifrado,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    consultor_receptor: ConsultorRespuestaReceptorHttp,
) -> Adaptadores:
    configuracion_asistente = _construir_configuracion_asistente()
    pasos = RegistradorPasos(fabrica_sesiones, RelojSistema())
    return Adaptadores(
        pasos=pasos,
        acreditacion=AdaptadorAcreditacionWeb(
            gestor_navegador,
            almacen_sesiones,
            AlmacenEvidenciasCifrado(
                configuracion.ruta_reportes, configuracion.clave_cifrado_evidencias
            ),
            pasos,
        ),
        consultor_receptor=consultor_receptor,
        sesion_plataforma=AdaptadorSesionPlataforma(
            gestor_navegador,
            almacen_sesiones,
            fabrica_sesiones,
            RelojSistema(),
            configuracion_asistente,
        ).con_pasos(pasos),
        validador_tedef_web=AdaptadorValidadorTedefWeb(
            gestor_navegador,
            almacen_sesiones,
            ConfiguracionValidadorTedefWeb(
                url_base=configuracion.tedef_web_url_base,
                tiempo_limite_validacion_segundos=configuracion.tiempo_limite_validacion_segundos,
                intervalo_poll_segundos=configuracion.intervalo_poll_validacion_segundos,
            ),
            RelojSistema(),
            pasos,
        ),
        comunicaciones=_construir_fuentes_comunicaciones(),
    )


async def main(una_vez: bool) -> None:
    motor = create_async_engine(configuracion.url_base_datos, pool_pre_ping=True)
    fabrica_sesiones = async_sessionmaker(bind=motor, expire_on_commit=False)
    consultor_receptor = ConsultorRespuestaReceptorHttp(configuracion.receptor_iafas_url_base)

    async with async_playwright() as playwright:
        gestor_navegador = GestorNavegador(
            playwright,
            configuracion.reinicios_navegador_cada_n_trabajos,
        )
        almacen_sesiones = AlmacenSesionesCifrado(
            configuracion.ruta_sesiones_plataformas, configuracion.clave_cifrado_sesiones
        )
        adaptadores = _construir_adaptadores(
            gestor_navegador, almacen_sesiones, fabrica_sesiones, consultor_receptor
        )

        registro.info("trabajador_iniciado", una_vez=una_vez)
        try:
            while True:
                proceso_algo = await _ciclo(fabrica_sesiones, adaptadores)
                if una_vez and proceso_algo:
                    break
                if not proceso_algo:
                    if una_vez:
                        registro.info("sin_trabajos_pendientes")
                        break
                    await asyncio.sleep(configuracion.intervalo_poll_segundos)
        finally:
            await gestor_navegador.cerrar()
            await motor.dispose()


if __name__ == "__main__":
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--una-vez", action="store_true", help="procesa un solo trabajo pendiente y termina"
    )
    argumentos = analizador.parse_args()
    asyncio.run(main(una_vez=argumentos.una_vez))
