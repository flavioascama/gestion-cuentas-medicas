"""Rutas de la ventana principal, Tablas de Validacion, Declaracion
Jurada (deshabilitada), Herramientas y administracion (Seccion 9.2, punto
3, y la ruta de administracion para forzar observaciones). Separado de
app/principal.py para no exceder el limite de complejidad ciclomatica de
GUIA_ESTILO_CODIGO.md (Seccion 3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from app.configuracion import configuracion
from app.criterios_simulados import DominioSimulado
from app.estado_falla import EstadoFalla
from app.reportes import generar_excel_dominio
from app.sesion import Sesion

RequerirSesionActiva = Callable[[Request], Sesion]
ContextoBase = Callable[[Sesion], dict[str, object]]


@dataclass(frozen=True, slots=True)
class DependenciasGenerales:
    dominios: tuple[DominioSimulado, ...]
    estado_falla: EstadoFalla


def _buscar_dominio(
    dominios: tuple[DominioSimulado, ...], tabla: str, campo: int
) -> DominioSimulado | None:
    return next((d for d in dominios if d.tabla == tabla and d.campo == campo), None)


def registrar_rutas_generales(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasGenerales,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    _registrar_rutas_menu(app, plantillas, requerir_sesion_activa, contexto_base)
    _registrar_rutas_tablas_validacion(app, plantillas, deps, requerir_sesion_activa, contexto_base)
    _registrar_rutas_admin(app, deps)


def _registrar_rutas_menu(
    app: FastAPI,
    plantillas: Jinja2Templates,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    @app.get("/menu", response_class=HTMLResponse)
    async def menu(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        return plantillas.TemplateResponse(request, "menu.html", contexto_base(sesion))

    @app.get("/declaracion-jurada", response_class=HTMLResponse)
    async def declaracion_jurada(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        return plantillas.TemplateResponse(
            request, "declaracion_jurada.html", contexto_base(sesion)
        )

    @app.get("/herramientas", response_class=HTMLResponse)
    async def herramientas(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        return plantillas.TemplateResponse(request, "herramientas.html", contexto_base(sesion))


def _registrar_rutas_tablas_validacion(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasGenerales,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    @app.get("/tablas-validacion", response_class=HTMLResponse)
    async def tablas_validacion(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        contexto = {**contexto_base(sesion), "dominios": deps.dominios}
        return plantillas.TemplateResponse(request, "tablas_validacion.html", contexto)

    # La ruta .xlsx se registra ANTES que /{tabla}/{campo}: ambas usan el
    # patron generico [^/]+ para {campo}, asi que si la ruta sin sufijo
    # se registrara primero, Starlette la haria calzar primero contra
    # ".../22.xlsx" (todo el segmento, incluido ".xlsx", como valor de
    # campo) antes de intentar la ruta mas especifica.
    @app.get("/tablas-validacion/{tabla}/{campo}.xlsx", response_model=None)
    async def descargar_dominio_xlsx(
        request: Request, tabla: str, campo: int
    ) -> Response | PlainTextResponse:
        requerir_sesion_activa(request)
        dominio = _buscar_dominio(deps.dominios, tabla, campo)
        if dominio is None:
            return PlainTextResponse("Tabla de validacion no encontrada.", status_code=404)
        contenido = generar_excel_dominio(dominio)
        return Response(
            content=contenido,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{tabla}_{campo}.xlsx"'},
        )

    @app.get("/tablas-validacion/{tabla}/{campo}", response_model=None)
    async def ver_dominio(
        request: Request, tabla: str, campo: int
    ) -> HTMLResponse | PlainTextResponse:
        sesion = requerir_sesion_activa(request)
        dominio = _buscar_dominio(deps.dominios, tabla, campo)
        if dominio is None:
            return PlainTextResponse("Tabla de validacion no encontrada.", status_code=404)
        contexto = {**contexto_base(sesion), "dominio": dominio}
        return plantillas.TemplateResponse(request, "ver_dominio.html", contexto)


def _registrar_rutas_admin(app: FastAPI, deps: DependenciasGenerales) -> None:
    @app.post("/admin/falla", response_model=None)
    async def fijar_falla(modo: str = Form(...)) -> PlainTextResponse:
        deps.estado_falla.fijar(modo)
        return PlainTextResponse(f"Modo de falla fijado a {modo!r}.")

    @app.get("/admin/falla", response_model=None)
    async def obtener_falla() -> PlainTextResponse:
        return PlainTextResponse(deps.estado_falla.modo)

    @app.get("/admin/configuracion", response_model=None)
    async def obtener_configuracion_simulador() -> JSONResponse:
        """Seccion 13 (Fase 20): la cabecera de los archivos de evidencia
        exige "la latencia artificial configurada de cada simulador
        durante esa ejecucion" -- expuesta aqui para que las herramientas
        de generacion de evidencia (que corren en otro contenedor, sin
        acceso a las variables de entorno de este proceso) la lean por
        HTTP en vez de asumir un valor fijo."""

        return JSONResponse({"latencia_artificial_ms": configuracion.latencia_artificial_ms})
