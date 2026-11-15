"""Portal web de respuestas (Seccion 9.2, punto 2): lista los lotes
recibidos y expone una ruta de administracion para forzar el estado."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.almacenamiento import AlmacenamientoReceptor
from app.auditoria import AuditoriaIafas, AuditoriaInvalidaError
from app.configuracion import configuracion

_RAIZ = Path(__file__).resolve().parent.parent
plantillas = Jinja2Templates(directory=str(_RAIZ / "plantillas"))


def construir_app(
    almacenamiento: AlmacenamientoReceptor, auditoria: AuditoriaIafas | None = None
) -> FastAPI:
    app = FastAPI(title="Simulador receptor IAFAS")
    auditoria = auditoria or AuditoriaIafas(configuracion.base_datos)
    _rutas_auditoria(app, auditoria)

    @app.get("/", response_class=HTMLResponse)
    async def listar_lotes(request: Request) -> HTMLResponse:
        lotes = almacenamiento.listar()
        return plantillas.TemplateResponse(request, "lotes.html", {"lotes": lotes})

    @app.get("/lotes/{nombre_archivo}", response_class=HTMLResponse)
    async def detalle_lote(request: Request, nombre_archivo: str) -> HTMLResponse:
        lote = almacenamiento.obtener(nombre_archivo)
        if lote is None:
            return HTMLResponse("Lote no encontrado.", status_code=404)
        return plantillas.TemplateResponse(request, "detalle_lote.html", {"lote": lote})

    @app.post("/admin/lotes/{nombre_archivo}/forzar", response_model=None)
    async def forzar_estado(
        nombre_archivo: str, estado: str = Form(...), motivo: str = Form("")
    ) -> HTMLResponse | RedirectResponse:
        if estado not in ("ACEPTADO", "RECHAZADO"):
            return HTMLResponse("Estado invalido.", status_code=400)
        encontrado = almacenamiento.forzar_estado(nombre_archivo, estado, motivo or None)
        if not encontrado:
            return HTMLResponse("Lote no encontrado.", status_code=404)
        return RedirectResponse(f"/lotes/{nombre_archivo}", status_code=303)

    return app


def _rutas_auditoria(app: FastAPI, auditoria: AuditoriaIafas) -> None:
    """Auditoria de la IAFAS (decision del auditor) y comunicaciones a la
    IPRESS, con el formulario de respuesta a una observacion."""

    @app.get("/auditoria", response_class=HTMLResponse)
    async def ver_auditoria(request: Request) -> HTMLResponse:
        return plantillas.TemplateResponse(
            request, "auditoria.html", {"documentos": auditoria.documentos()}
        )

    @app.post("/admin/documentos/{documento}/auditoria", response_model=None)
    async def auditar(  # noqa: PLR0913 - campos del formulario del auditor
        documento: str,
        resultado: str = Form(...),
        canal: str = Form("PORTAL"),
        motivo_codigo: str = Form(""),
        monto_glosado: str = Form(""),
        detalle: str = Form(""),
        decision_respuesta: str = Form("ACEPTAR"),
    ) -> HTMLResponse | RedirectResponse:
        try:
            auditoria.auditar(
                documento,
                resultado,
                canal,
                motivo_codigo or None,
                Decimal(monto_glosado) if monto_glosado else None,
                detalle or None,
                decision_respuesta,
            )
        except (AuditoriaInvalidaError, InvalidOperation) as error:
            return HTMLResponse(str(error), status_code=400)
        return RedirectResponse("/auditoria", status_code=303)

    @app.get("/comunicaciones", response_class=HTMLResponse)
    async def listar_comunicaciones(request: Request, ipress: str | None = None) -> HTMLResponse:
        return plantillas.TemplateResponse(
            request, "comunicaciones.html", {"comunicaciones": auditoria.comunicaciones(ipress)}
        )

    @app.get("/comunicaciones/{codigo}", response_class=HTMLResponse)
    async def ver_comunicacion(request: Request, codigo: str) -> HTMLResponse:
        comunicacion = auditoria.comunicacion(codigo)
        if comunicacion is None:
            return HTMLResponse("Comunicacion no encontrada.", status_code=404)
        datos_json = json.dumps(comunicacion.datos, ensure_ascii=False).replace("</", "<\\/")
        return plantillas.TemplateResponse(
            request,
            "detalle_comunicacion.html",
            {"c": comunicacion, "datos_json": datos_json},
        )

    @app.post("/comunicaciones/{codigo}/respuesta", response_model=None)
    async def responder(
        codigo: str,
        codigo_ipress: str = Form(...),
        respuesta: str = Form(...),
        sustento: str = Form(""),
    ) -> HTMLResponse | RedirectResponse:
        try:
            auditoria.responder(codigo, codigo_ipress, respuesta, sustento or None)
        except AuditoriaInvalidaError as error:
            return HTMLResponse(str(error), status_code=400)
        return RedirectResponse(f"/comunicaciones/{codigo}", status_code=303)


def crear_app_desde_configuracion() -> FastAPI:
    return construir_app(AlmacenamientoReceptor(configuracion.base_datos))
