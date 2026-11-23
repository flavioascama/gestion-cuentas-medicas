"""Portal web de respuestas (Seccion 9.2, punto 2): lista los lotes
recibidos; la IAFAS acepta o rechaza cada uno una sola vez y audita los
comprobantes del lote aceptado dentro del propio lote.

Cada aseguradora tiene su propio portal bajo `/aseguradora/<codigo>`, con
su razon social y solo sus lotes, auditorias y comunicaciones (2026-11-17:
el sistema deja elegir entre varias IAFAS y antes habia un unico portal
para todas). Es un solo proceso: el nombre del archivo recibido lleva el
codigo de la IAFAS y con el se sabe a que portal pertenece.

Las rutas sin aseguradora (`/lotes/<archivo>`, `/comunicaciones...`,
`/admin/...`) son las que consulta el sistema por programa y no cambian.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.almacenamiento import AlmacenamientoReceptor, LoteRecibido
from app.auditoria import AuditoriaIafas, AuditoriaInvalidaError, Comunicacion
from app.configuracion import configuracion
from app.correo import EnviadorCorreoSmtp, leer_recibidos, remitente_de

_RAIZ = Path(__file__).resolve().parent.parent
plantillas = Jinja2Templates(directory=str(_RAIZ / "plantillas"))

_ZONA_PERU = timezone(timedelta(hours=-5))


def _hora_lima(valor: object) -> str:
    """Las fechas se guardan con la hora del servidor; el portal las
    muestra con la hora de Lima."""
    try:
        instante = datetime.fromisoformat(str(valor))
    except ValueError:
        return str(valor)
    return instante.astimezone(_ZONA_PERU).strftime("%Y-%m-%d %H:%M:%S")


plantillas.env.filters["hora_lima"] = _hora_lima

# Catalogo de motivos de observacion que la IPRESS reconoce.
MOTIVOS_OBSERVACION = (
    ("OBS-01", "Datos incompletos"),
    ("OBS-02", "Ausencia de firma"),
    ("OBS-03", "Paciente no activo en la cobertura"),
    ("OBS-04", "Prestación no reconocida"),
    ("OBS-05", "Incompatibilidad entre el diagnóstico y el procedimiento"),
    ("OBS-06", "Duplicidad de registros"),
    ("OBS-07", "Prestaciones fuera de la cobertura del plan"),
)
plantillas.env.globals["motivos_observacion"] = MOTIVOS_OBSERVACION

_PREFIJO_PORTAL = "/aseguradora/"


def cargar_aseguradoras(ruta: Path) -> dict[str, str]:
    """Codigo -> razon social, del maestro sintetico de IAFAS que comparte
    el sistema (`datos_semilla/iafas.json`). Sin ese archivo no hay
    portales por aseguradora y la entrada queda vacia."""
    if not ruta.is_file():
        return {}
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    return {fila["codigo"]: fila["razon_social"] for fila in contenido["iafas"]}


def _volver(volver: str, por_defecto: str) -> str:
    """Solo se regresa a un portal de este mismo sitio."""
    return volver if volver.startswith(_PREFIJO_PORTAL) else por_defecto


@dataclass(frozen=True, slots=True)
class _Portal:
    almacenamiento: AlmacenamientoReceptor
    auditoria: AuditoriaIafas
    enviador: EnviadorCorreoSmtp | None
    aseguradoras: dict[str, str]

    def contexto(self, codigo: str) -> dict[str, Any]:
        """Lo que toda pantalla de un portal necesita: de quien es y con
        que prefijo se arman sus enlaces."""
        razon_social = self.aseguradoras.get(codigo)
        if razon_social is None:
            raise HTTPException(status_code=404, detail="Aseguradora no encontrada.")
        return {
            "aseguradora": {"codigo": codigo, "razon_social": razon_social},
            "prefijo": f"{_PREFIJO_PORTAL}{codigo}",
        }

    def datos_lote(self, lote: LoteRecibido) -> dict[str, Any]:
        """El lote con sus comprobantes: se auditan dentro de el."""
        propios = [
            d for d in self.auditoria.documentos() if d.nombre_archivo == lote.nombre_archivo
        ]
        return {"lote": lote, "documentos": propios}


def construir_app(
    almacenamiento: AlmacenamientoReceptor,
    auditoria: AuditoriaIafas | None = None,
    enviador: EnviadorCorreoSmtp | None = None,
    aseguradoras: dict[str, str] | None = None,
) -> FastAPI:
    app = FastAPI(title="Simulador receptor IAFAS")
    auditoria = auditoria or AuditoriaIafas(configuracion.base_datos)
    portal = _Portal(almacenamiento, auditoria, enviador, aseguradoras or {})
    _rutas_auditoria(app, portal)
    _rutas_correo(app, enviador)
    _rutas_portal_lotes(app, portal)
    _rutas_portal_auditoria(app, portal)

    @app.get("/", response_class=HTMLResponse)
    async def elegir_aseguradora(request: Request) -> HTMLResponse:
        lotes = almacenamiento.listar()
        filas = [
            {
                "codigo": codigo,
                "razon_social": razon_social,
                "lotes": sum(1 for lote in lotes if lote.codigo_iafas == codigo),
            }
            for codigo, razon_social in sorted(portal.aseguradoras.items(), key=lambda par: par[1])
        ]
        return plantillas.TemplateResponse(request, "inicio.html", {"aseguradoras": filas})

    @app.get("/lotes/{nombre_archivo}", response_class=HTMLResponse)
    async def detalle_lote(request: Request, nombre_archivo: str) -> HTMLResponse:
        lote = almacenamiento.obtener(nombre_archivo)
        if lote is None:
            return HTMLResponse("Lote no encontrado.", status_code=404)
        return plantillas.TemplateResponse(request, "detalle_lote.html", portal.datos_lote(lote))

    @app.post("/admin/lotes/{nombre_archivo}/respuesta", response_model=None)
    async def responder_lote(
        nombre_archivo: str,
        estado: str = Form(...),
        motivo: str = Form(""),
        volver: str = Form(""),
    ) -> HTMLResponse | RedirectResponse:
        motivo = motivo.strip()
        if estado not in ("ACEPTADO", "RECHAZADO"):
            return HTMLResponse("Respuesta no válida.", status_code=400)
        if estado == "RECHAZADO" and not motivo:
            return HTMLResponse("El rechazo necesita un motivo.", status_code=400)
        if almacenamiento.obtener(nombre_archivo) is None:
            return HTMLResponse("Lote no encontrado.", status_code=404)
        if not almacenamiento.responder(nombre_archivo, estado, motivo or None):
            return HTMLResponse("El lote ya fue respondido.", status_code=409)
        return RedirectResponse(_volver(volver, f"/lotes/{nombre_archivo}"), status_code=303)

    return app


def _rutas_portal_lotes(app: FastAPI, portal: _Portal) -> None:
    """Portal de una aseguradora: sus lotes recibidos y su correo."""

    @app.get(_PREFIJO_PORTAL + "{codigo}", response_class=HTMLResponse)
    async def lotes_de_aseguradora(request: Request, codigo: str) -> HTMLResponse:
        contexto = portal.contexto(codigo)
        lotes = [lote for lote in portal.almacenamiento.listar() if lote.codigo_iafas == codigo]
        return plantillas.TemplateResponse(request, "lotes.html", contexto | {"lotes": lotes})

    @app.get(_PREFIJO_PORTAL + "{codigo}/lotes/{nombre_archivo}", response_class=HTMLResponse)
    async def detalle_lote_de_aseguradora(
        request: Request, codigo: str, nombre_archivo: str
    ) -> HTMLResponse:
        contexto = portal.contexto(codigo)
        lote = portal.almacenamiento.obtener(nombre_archivo)
        if lote is None or lote.codigo_iafas != codigo:
            return HTMLResponse("Lote no encontrado.", status_code=404)
        return plantillas.TemplateResponse(
            request, "detalle_lote.html", contexto | portal.datos_lote(lote)
        )

    @app.get(_PREFIJO_PORTAL + "{codigo}/correo", response_class=HTMLResponse)
    async def correo_de_aseguradora(
        request: Request, codigo: str, enviado: str | None = None
    ) -> HTMLResponse:
        contexto = portal.contexto(codigo)
        return plantillas.TemplateResponse(
            request, "correo.html", contexto | _datos_correo(portal.enviador, enviado, codigo)
        )


def _rutas_portal_auditoria(app: FastAPI, portal: _Portal) -> None:
    """Portal de una aseguradora: sus comunicaciones."""

    @app.get(_PREFIJO_PORTAL + "{codigo}/comunicaciones", response_class=HTMLResponse)
    async def comunicaciones_de_aseguradora(request: Request, codigo: str) -> HTMLResponse:
        contexto = portal.contexto(codigo)
        propias = [c for c in portal.auditoria.comunicaciones() if c.codigo_iafas == codigo]
        return plantillas.TemplateResponse(
            request, "comunicaciones.html", contexto | {"comunicaciones": propias}
        )

    @app.get(
        _PREFIJO_PORTAL + "{codigo}/comunicaciones/{comunicacion}", response_class=HTMLResponse
    )
    async def comunicacion_de_aseguradora(
        request: Request, codigo: str, comunicacion: str
    ) -> HTMLResponse:
        contexto = portal.contexto(codigo)
        encontrada = portal.auditoria.comunicacion(comunicacion)
        if encontrada is None or encontrada.codigo_iafas != codigo:
            return HTMLResponse("Comunicacion no encontrada.", status_code=404)
        return plantillas.TemplateResponse(
            request, "detalle_comunicacion.html", contexto | _datos_comunicacion(encontrada)
        )


def _datos_comunicacion(comunicacion: Comunicacion) -> dict[str, Any]:
    datos_json = json.dumps(comunicacion.datos, ensure_ascii=False).replace("</", "<\\/")
    return {"c": comunicacion, "datos_json": datos_json}


def _datos_correo(
    enviador: EnviadorCorreoSmtp | None, enviado: str | None, codigo_iafas: str | None = None
) -> dict[str, Any]:
    remitente = remitente_de(configuracion.correo_remitente, codigo_iafas)
    recibidos = (
        leer_recibidos(configuracion.smtp_host, configuracion.imap_puerto, remitente)
        if enviador is not None and codigo_iafas
        else []
    )
    return {
        "disponible": enviador is not None,
        "enviado": enviado == "1",
        "remitente": remitente,
        "destinatario": configuracion.correo_destino_ipress,
        "recibidos": recibidos,
    }


def _rutas_auditoria(app: FastAPI, portal: _Portal) -> None:
    """Auditoria de la IAFAS (decision del auditor sobre un comprobante de
    un lote aceptado) y comunicaciones a la IPRESS, con el formulario de
    respuesta a una observacion."""
    auditoria = portal.auditoria

    @app.post("/admin/documentos/{documento}/auditoria", response_model=None)
    async def auditar(  # noqa: PLR0913 - campos del formulario del auditor
        documento: str,
        resultado: str = Form(...),
        canal: str = Form("PORTAL"),
        motivo_codigo: str = Form(""),
        monto_glosado: str = Form(""),
        detalle: str = Form(""),
        decision_respuesta: str = Form("ACEPTAR"),
        volver: str = Form(""),
    ) -> HTMLResponse | RedirectResponse:
        propio = next((d for d in auditoria.documentos() if d.documento == documento), None)
        archivo = propio.nombre_archivo if propio is not None else ""
        lote = portal.almacenamiento.obtener(archivo)
        if propio is not None and (lote is None or lote.estado != "ACEPTADO"):
            return HTMLResponse("El lote del comprobante no está aceptado.", status_code=400)
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
        return RedirectResponse(_volver(volver, f"/lotes/{archivo}"), status_code=303)

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
        return plantillas.TemplateResponse(
            request, "detalle_comunicacion.html", _datos_comunicacion(comunicacion)
        )

    @app.post("/comunicaciones/{codigo}/respuesta", response_model=None)
    async def responder(  # noqa: PLR0913 - formulario de la respuesta
        codigo: str,
        codigo_ipress: str = Form(...),
        respuesta: str = Form(...),
        sustento: str = Form(""),
        comprobante_vigente: str = Form(""),
        monto_vigente: str = Form(""),
        volver: str = Form(""),
        adjunto: UploadFile | None = None,
    ) -> HTMLResponse | RedirectResponse:
        try:
            refacturado = (
                (comprobante_vigente, Decimal(monto_vigente))
                if comprobante_vigente and monto_vigente
                else None
            )
            auditoria.responder(codigo, codigo_ipress, respuesta, sustento or None, refacturado)
        except (AuditoriaInvalidaError, InvalidOperation) as error:
            return HTMLResponse(str(error), status_code=400)
        if adjunto is not None and adjunto.filename:
            auditoria.adjuntar(codigo, adjunto.filename, await adjunto.read())
        return RedirectResponse(_volver(volver, f"/comunicaciones/{codigo}"), status_code=303)

    @app.get("/comunicaciones/{codigo}/adjunto", response_model=None)
    async def descargar_adjunto(codigo: str) -> Response:
        adjunto = auditoria.adjunto(codigo)
        if adjunto is None:
            return HTMLResponse("La respuesta no tiene un documento adjunto.", status_code=404)
        nombre, contenido = adjunto
        return Response(
            content=contenido,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nombre)}"},
        )


def _rutas_correo(app: FastAPI, enviador: EnviadorCorreoSmtp | None) -> None:
    """Correo libre a la IPRESS: el que la aseguradora escribe fuera de su
    formato de comunicaciones, con o sin un documento adjunto."""

    @app.get("/correo", response_class=HTMLResponse)
    async def ver_correo(request: Request, enviado: str | None = None) -> HTMLResponse:
        return plantillas.TemplateResponse(request, "correo.html", _datos_correo(enviador, enviado))

    @app.post("/admin/correo", response_model=None)
    async def enviar_correo(
        asunto: str = Form(...),
        texto: str = Form(...),
        adjuntar_documento: str = Form(""),
        volver: str = Form(""),
    ) -> HTMLResponse | RedirectResponse:
        if enviador is None:
            return HTMLResponse("El servidor de correo no está configurado.", status_code=503)
        # El portal de cada aseguradora manda su direccion de regreso.
        codigo_iafas = (
            volver.removeprefix(_PREFIJO_PORTAL).split("/")[0]
            if volver.startswith(_PREFIJO_PORTAL)
            else None
        )
        try:
            enviador.enviar_libre(
                asunto.strip(), texto.strip(), bool(adjuntar_documento), codigo_iafas
            )
        except OSError as error:
            return HTMLResponse(f"No se pudo enviar el correo: {error}", status_code=502)
        return RedirectResponse(f"{_volver(volver, '/correo')}?enviado=1", status_code=303)


def crear_app_desde_configuracion() -> FastAPI:
    return construir_app(
        AlmacenamientoReceptor(configuracion.base_datos),
        aseguradoras=cargar_aseguradoras(configuracion.datos_semilla / "iafas.json"),
    )
