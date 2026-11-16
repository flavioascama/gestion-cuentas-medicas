"""Simulador TEDEF Web (Seccion 9.2): arma la aplicacion FastAPI con las
pantallas del alcance (ingreso con CAPTCHA, seleccionar perfil, seleccionar
entidad, ventana principal, Monitoreo de Lotes, Tablas de Validacion,
Declaracion Jurada deshabilitada, Herramientas)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.almacenamiento import AlmacenamientoTedefWeb
from app.anexo1 import cargar_tablas
from app.captcha import GestorCaptcha
from app.configuracion import configuracion
from app.criterios_simulados import cargar_dominios_simulados
from app.datos import cargar_claves_iafas, cargar_ipress_propia, cargar_maestro_iafas
from app.estado_falla import EstadoFalla
from app.rutas_generales import DependenciasGenerales, registrar_rutas_generales
from app.rutas_ingreso import DependenciasIngreso, registrar_rutas_ingreso
from app.rutas_lotes import DependenciasLotes, registrar_rutas_lotes
from app.sesion import NOMBRE_COOKIE, ErrorSesionInvalida, GestorSesiones, Sesion

_RAIZ = Path(__file__).resolve().parent.parent
plantillas = Jinja2Templates(directory=str(_RAIZ / "plantillas"))


def construir_app(almacenamiento: AlmacenamientoTedefWeb) -> FastAPI:
    app = FastAPI(title="Simulador TEDEF Web")
    app.mount("/estaticos", StaticFiles(directory=str(_RAIZ / "estaticos")), name="estaticos")
    gestor_sesiones = GestorSesiones(configuracion.sesion_expiracion_minutos)
    gestor_captcha = GestorCaptcha()
    estado_falla = EstadoFalla(configuracion.modo_falla_inicial)

    tablas_anexo1 = cargar_tablas(configuracion.docs_fuentes)
    dominios = cargar_dominios_simulados()
    ipress_propia = cargar_ipress_propia(configuracion.maestros_sinteticos)
    maestro_iafas = cargar_maestro_iafas(configuracion.maestros_sinteticos)
    claves_iafas = cargar_claves_iafas(configuracion.datos_semilla)

    def requerir_sesion(request: Request) -> Sesion:
        sesion = gestor_sesiones.validar(request.cookies.get(NOMBRE_COOKIE))
        if sesion is None:
            raise ErrorSesionInvalida()
        return sesion

    def requerir_sesion_activa(request: Request) -> Sesion:
        sesion = requerir_sesion(request)
        if not sesion.activa:
            raise ErrorSesionInvalida()
        return sesion

    def contexto_base(sesion: Sesion) -> dict[str, object]:
        return {"usuario": sesion.usuario, "perfil": sesion.perfil, "ipress": ipress_propia}

    @app.exception_handler(ErrorSesionInvalida)
    async def manejar_sesion_invalida(
        request: Request, exc: ErrorSesionInvalida
    ) -> RedirectResponse:
        return RedirectResponse("/ingreso", status_code=303)

    @app.middleware("http")
    async def middleware_simulacion(request: Request, call_next):  # type: ignore[no-untyped-def]
        if configuracion.latencia_artificial_ms > 0:
            await asyncio.sleep(configuracion.latencia_artificial_ms / 1000)
        return await call_next(request)  # type: ignore[no-any-return]

    registrar_rutas_ingreso(
        app,
        plantillas,
        DependenciasIngreso(gestor_sesiones, gestor_captcha, ipress_propia),
        requerir_sesion,
    )
    registrar_rutas_generales(
        app,
        plantillas,
        DependenciasGenerales(dominios, estado_falla),
        requerir_sesion_activa,
        contexto_base,
    )
    registrar_rutas_lotes(
        app,
        plantillas,
        DependenciasLotes(
            almacenamiento=almacenamiento,
            tablas_anexo1=tablas_anexo1,
            dominios=dominios,
            ipress_propia=ipress_propia,
            maestro_iafas=maestro_iafas,
            claves_iafas=claves_iafas,
            estado_falla=estado_falla,
        ),
        requerir_sesion_activa,
        contexto_base,
    )

    return app


def crear_app_desde_configuracion() -> FastAPI:
    """Punto de entrada perezoso para uvicorn (`--factory`): construir la
    app aqui, y no en una variable de modulo, evita que importar este
    archivo (por ejemplo, desde las pruebas) intente leer el Anexo 1 y los
    maestros sinteticos antes de tiempo."""

    almacenamiento = AlmacenamientoTedefWeb(configuracion.base_datos)
    return construir_app(almacenamiento)
