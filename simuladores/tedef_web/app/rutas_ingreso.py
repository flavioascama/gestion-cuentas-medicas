"""Rutas de ingreso, CAPTCHA, seleccion de perfil y de entidad (Seccion
9.2, puntos 1 y 2). Separado de app/principal.py para no exceder el
limite de complejidad ciclomatica de GUIA_ESTILO_CODIGO.md (Seccion 3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.captcha import GestorCaptcha
from app.configuracion import configuracion
from app.datos import IpressPropia
from app.sesion import NOMBRE_COOKIE, PERFILES_VALIDOS, GestorSesiones, Sesion

RequerirSesion = Callable[[Request], Sesion]


@dataclass(frozen=True, slots=True)
class DependenciasIngreso:
    gestor_sesiones: GestorSesiones
    gestor_captcha: GestorCaptcha
    ipress_propia: IpressPropia


def _pagina_credenciales_invalidas(
    plantillas: Jinja2Templates, request: Request, deps: DependenciasIngreso
) -> HTMLResponse:
    nuevo = deps.gestor_captcha.generar()
    return plantillas.TemplateResponse(
        request,
        "ingreso.html",
        {"captcha_id": nuevo.id, "error": "Usuario o contraseña incorrecta."},
        status_code=401,
    )


def registrar_rutas_ingreso(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasIngreso,
    requerir_sesion: RequerirSesion,
) -> None:
    _registrar_rutas_credenciales(app, plantillas, deps)
    _registrar_rutas_perfil_y_entidad(app, plantillas, deps, requerir_sesion)


def _registrar_rutas_credenciales(
    app: FastAPI, plantillas: Jinja2Templates, deps: DependenciasIngreso
) -> None:
    @app.get("/", response_model=None)
    async def raiz(request: Request) -> RedirectResponse:
        sesion = deps.gestor_sesiones.validar(request.cookies.get(NOMBRE_COOKIE))
        return RedirectResponse("/menu" if sesion and sesion.activa else "/ingreso")

    @app.get("/ingreso", response_class=HTMLResponse)
    async def formulario_ingreso(request: Request) -> HTMLResponse:
        captcha = deps.gestor_captcha.generar()
        return plantillas.TemplateResponse(request, "ingreso.html", {"captcha_id": captcha.id})

    @app.get("/captcha/{captcha_id}.png", response_model=None)
    async def imagen_captcha(captcha_id: str) -> Response | PlainTextResponse:
        imagen = deps.gestor_captcha.imagen_png(captcha_id)
        if imagen is None:
            return PlainTextResponse("CAPTCHA vencido.", status_code=404)
        return Response(content=imagen, media_type="image/png")

    @app.post("/ingreso", response_model=None)
    async def procesar_ingreso(
        request: Request,
        usuario: str = Form(...),
        clave: str = Form(...),
        captcha_id: str = Form(...),
        respuesta_captcha: str = Form(...),
    ) -> HTMLResponse | RedirectResponse:
        if not deps.gestor_captcha.verificar_y_consumir(captcha_id, respuesta_captcha):
            return _pagina_credenciales_invalidas(plantillas, request, deps)
        if usuario != configuracion.usuario or clave != configuracion.clave:
            return _pagina_credenciales_invalidas(plantillas, request, deps)
        sesion = deps.gestor_sesiones.iniciar(usuario)
        respuesta = RedirectResponse("/seleccionar-perfil", status_code=303)
        respuesta.set_cookie(NOMBRE_COOKIE, sesion.token, httponly=True, samesite="lax")
        return respuesta

    @app.post("/salir", response_model=None)
    async def salir(request: Request) -> RedirectResponse:
        token = request.cookies.get(NOMBRE_COOKIE)
        if token:
            deps.gestor_sesiones.cerrar(token)
        respuesta = RedirectResponse("/ingreso", status_code=303)
        respuesta.delete_cookie(NOMBRE_COOKIE)
        return respuesta

    _registrar_rutas_admin_captcha(app, deps)


def _registrar_rutas_admin_captcha(app: FastAPI, deps: DependenciasIngreso) -> None:
    """Fase 20: separado de `_registrar_rutas_credenciales` para no
    superar el limite de complejidad ciclomatica de esa funcion
    (GUIA_ESTILO_CODIGO.md, Seccion 3)."""

    @app.get("/admin/captcha/{captcha_id}", response_model=None)
    async def obtener_texto_captcha(captcha_id: str) -> PlainTextResponse:
        """Seccion 8.4: "ruta de administracion que devuelve el texto del
        CAPTCHA vigente solo si SIMULADOR_MODO_PRUEBA=true; la prueba
        actua como el usuario humano llamando a la API del sistema, nunca
        el robot" -- el robot de sesion asistida jamas llama esta ruta."""

        if not configuracion.simulador_modo_prueba:
            return PlainTextResponse("No disponible.", status_code=403)
        texto = deps.gestor_captcha.texto_vigente(captcha_id)
        if texto is None:
            return PlainTextResponse("CAPTCHA no encontrado o vencido.", status_code=404)
        return PlainTextResponse(texto)

    @app.get("/admin/captcha", response_model=None)
    async def obtener_texto_captcha_mas_reciente() -> PlainTextResponse:
        """Fase 20: variante sin id de arriba (ver su docstring)."""

        if not configuracion.simulador_modo_prueba:
            return PlainTextResponse("No disponible.", status_code=403)
        texto = deps.gestor_captcha.texto_del_mas_reciente()
        if texto is None:
            return PlainTextResponse("No hay ningun CAPTCHA vigente.", status_code=404)
        return PlainTextResponse(texto)


def _registrar_rutas_perfil_y_entidad(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasIngreso,
    requerir_sesion: RequerirSesion,
) -> None:
    @app.get("/seleccionar-perfil", response_class=HTMLResponse)
    async def formulario_perfil(request: Request) -> HTMLResponse:
        requerir_sesion(request)
        return plantillas.TemplateResponse(
            request, "seleccionar_perfil.html", {"perfiles": PERFILES_VALIDOS}
        )

    @app.post("/seleccionar-perfil", response_model=None)
    async def procesar_perfil(request: Request, perfil: str = Form(...)) -> RedirectResponse:
        sesion = requerir_sesion(request)
        deps.gestor_sesiones.seleccionar_perfil(sesion.token, perfil)
        return RedirectResponse("/seleccionar-entidad", status_code=303)

    @app.get("/seleccionar-entidad", response_class=HTMLResponse)
    async def formulario_entidad(request: Request) -> HTMLResponse:
        requerir_sesion(request)
        return plantillas.TemplateResponse(
            request, "seleccionar_entidad.html", {"ipress": deps.ipress_propia}
        )

    @app.post("/seleccionar-entidad", response_model=None)
    async def procesar_entidad(request: Request) -> RedirectResponse:
        sesion = requerir_sesion(request)
        deps.gestor_sesiones.seleccionar_entidad(sesion.token)
        return RedirectResponse("/menu", status_code=303)
