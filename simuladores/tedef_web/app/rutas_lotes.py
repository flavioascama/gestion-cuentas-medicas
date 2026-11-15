"""Rutas de Monitoreo de Lotes (Seccion 9.2, puntos 4 a 6): Lotes por
Validar, Lotes por Enviar, Lotes Enviados a SUSALUD, Lotes Eliminados.
Separado de app/principal.py para no exceder el limite de longitud de
archivo de GUIA_ESTILO_CODIGO.md (Seccion 3)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.almacenamiento import AlmacenamientoTedefWeb, LoteDB
from app.anexo1 import TablaAnexo1
from app.cifrado import cifrar_archivos
from app.configuracion import configuracion
from app.criterios_simulados import DominioSimulado
from app.datos import IpressPropia, MaestroIafas
from app.estado_falla import EstadoFalla
from app.nombrado import nombre_archivo_s01
from app.reportes import (
    EncabezadoReporte,
    generar_reporte_clave_valor,
    generar_reporte_observaciones_forma,
    generar_reporte_validacion_detallada,
)
from app.revision_forma import ObservacionForma, lineas_de, revisar_forma
from app.sesion import Sesion
from app.validacion_detallada import ObservacionDetallada, validar_detallada


@dataclass(frozen=True, slots=True)
class DependenciasLotes:
    almacenamiento: AlmacenamientoTedefWeb
    tablas_anexo1: dict[str, TablaAnexo1]
    dominios: tuple[DominioSimulado, ...]
    ipress_propia: IpressPropia
    maestro_iafas: tuple[MaestroIafas, ...]
    claves_iafas: dict[str, str]
    estado_falla: EstadoFalla


def _filtrar(lotes: list[LoteDB], request: Request) -> list[LoteDB]:
    parametros = request.query_params
    numero_lote = parametros.get("numero_lote") or None
    periodo = parametros.get("periodo") or None
    desde = parametros.get("desde") or None
    hasta = parametros.get("hasta") or None
    resultado = lotes
    if numero_lote:
        resultado = [lote for lote in resultado if lote.identidad.numero_lote == numero_lote]
    if periodo:
        resultado = [lote for lote in resultado if lote.identidad.periodo == periodo]
    if desde:
        resultado = [lote for lote in resultado if lote.registrado_en[:10] >= desde]
    if hasta:
        resultado = [lote for lote in resultado if lote.registrado_en[:10] <= hasta]
    return resultado


def _encabezado(deps: DependenciasLotes, lote: LoteDB, sesion: Sesion) -> EncabezadoReporte:
    return EncabezadoReporte(
        ipress=deps.ipress_propia,
        codigo_iafas=lote.identidad.codigo_iafas,
        numero_lote=lote.identidad.numero_lote,
        usuario=sesion.usuario,
        perfil=sesion.perfil or "-",
    )


def _resolver_uno(deps: DependenciasLotes, lote: LoteDB) -> None:
    archivos = deps.almacenamiento.archivos_de(lote.id)
    lineas_por_tabla = {
        tabla: (lineas_de(contenido) or []) for tabla, _nombre, contenido in archivos
    }
    observaciones = validar_detallada(lineas_por_tabla, deps.tablas_anexo1, deps.dominios)
    if deps.estado_falla.modo == "forzar_observaciones" and not observaciones:
        observaciones = [
            ObservacionDetallada(
                "T1",
                1,
                "documento facturador",
                "(forzado por administracion)",
                "",
                "SIM-FORZADO",
                "Observacion forzada por la ruta de administracion (Seccion 9.2).",
            )
        ]
    if observaciones:
        deps.almacenamiento.registrar_observaciones_detalladas(lote.id, observaciones)
        deps.almacenamiento.marcar_observado_detallada(lote.id)
        return

    componentes = {
        "ruc": lote.identidad.ruc,
        "ipress": lote.identidad.codigo_ipress,
        "iafas": lote.identidad.codigo_iafas,
        "lote": lote.identidad.numero_lote,
        "periodo": lote.identidad.periodo,
        "fecha": lote.identidad.fecha,
    }
    nombre_s01 = nombre_archivo_s01(componentes)
    contrasena = deps.claves_iafas[lote.identidad.codigo_iafas]
    contenido_s01 = cifrar_archivos(
        {nombre: contenido for _t, nombre, contenido in archivos}, contrasena
    )
    deps.almacenamiento.marcar_validado(lote.id, nombre_s01, contenido_s01)


def _resolver_pendientes(deps: DependenciasLotes) -> None:
    ahora = datetime.now()
    for lote in deps.almacenamiento.listar_por_validar():
        if lote.estado != "VALIDANDO" or lote.validar_listo_en is None:
            continue
        if ahora >= datetime.fromisoformat(lote.validar_listo_en):
            _resolver_uno(deps, lote)


async def _leer_archivos_subidos(archivos: list[UploadFile]) -> dict[str, bytes]:
    resultado = {}
    for archivo in archivos:
        assert isinstance(archivo, StarletteUploadFile)
        nombre = archivo.filename or ""
        resultado[nombre] = await archivo.read()
    return resultado


RequerirSesionActiva = Callable[[Request], Sesion]
ContextoBase = Callable[[Sesion], dict[str, object]]


def registrar_rutas_lotes(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasLotes,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    _registrar_lotes_por_validar(app, plantillas, deps, requerir_sesion_activa, contexto_base)
    _registrar_lotes_por_enviar(app, plantillas, deps, requerir_sesion_activa, contexto_base)
    _registrar_lotes_solo_consulta(app, plantillas, deps, requerir_sesion_activa, contexto_base)


def _registrar_lotes_por_validar(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasLotes,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    _registrar_lotes_por_validar_listado(
        app, plantillas, deps, requerir_sesion_activa, contexto_base
    )
    _registrar_lotes_por_validar_acciones(app, deps, requerir_sesion_activa)


def _registrar_lotes_por_validar_listado(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasLotes,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    @app.get("/lotes-por-validar", response_class=HTMLResponse)
    async def lotes_por_validar(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        _resolver_pendientes(deps)
        lotes = _filtrar(deps.almacenamiento.listar_por_validar(), request)
        contexto = {**contexto_base(sesion), "lotes": lotes}
        return plantillas.TemplateResponse(request, "lotes_por_validar.html", contexto)

    @app.get("/lotes-por-validar/nuevo", response_class=HTMLResponse)
    async def nuevo_registro(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        return plantillas.TemplateResponse(request, "nuevo_registro.html", contexto_base(sesion))

    @app.post("/lotes-por-validar/registrar", response_class=HTMLResponse)
    async def registrar_archivos(request: Request, archivos: list[UploadFile]) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        contenidos = await _leer_archivos_subidos(archivos)
        resultado = revisar_forma(
            contenidos,
            deps.tablas_anexo1,
            deps.ipress_propia,
            frozenset(m.codigo for m in deps.maestro_iafas),
            ya_registrado=deps.almacenamiento.existe_lote_activo,
        )

        lote_id = None
        if resultado.identidad is not None:
            estado = "REGISTRADO" if resultado.conforme else "RECHAZADO_FORMA"
            lote_id = deps.almacenamiento.registrar_intento(
                resultado.identidad, estado, resultado.archivos_por_tabla, sesion.usuario
            )
            if resultado.observaciones:
                deps.almacenamiento.registrar_observaciones_forma(lote_id, resultado.observaciones)

        contexto = {
            **contexto_base(sesion),
            "conforme": resultado.conforme,
            "lote_id": lote_id,
            "observaciones": resultado.observaciones,
        }
        return plantillas.TemplateResponse(request, "resultado_registro.html", contexto)

    @app.get("/lotes-por-validar/{lote_id}/detalle", response_class=HTMLResponse)
    async def detalle_por_validar(request: Request, lote_id: int) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        lote = deps.almacenamiento.obtener(lote_id)
        archivos = deps.almacenamiento.archivos_de(lote_id) if lote else []
        contexto = {
            **contexto_base(sesion),
            "lote": lote,
            "archivos": archivos,
            "volver": "/lotes-por-validar",
        }
        return plantillas.TemplateResponse(request, "detalle_lote.html", contexto)


def _registrar_lotes_por_validar_acciones(
    app: FastAPI, deps: DependenciasLotes, requerir_sesion_activa: RequerirSesionActiva
) -> None:
    @app.get("/lotes-por-validar/{lote_id}/observaciones-forma.xlsx", response_model=None)
    async def observaciones_forma_xlsx(
        request: Request, lote_id: int
    ) -> Response | PlainTextResponse:
        sesion = requerir_sesion_activa(request)
        lote = deps.almacenamiento.obtener(lote_id)
        if lote is None:
            return PlainTextResponse("Lote no encontrado.", status_code=404)
        filas = deps.almacenamiento.observaciones_de(lote_id, "FORMA")
        observaciones = tuple(
            ObservacionForma(f["tabla"], f["codigo_error"], f["descripcion"]) for f in filas
        )
        contenido = generar_reporte_observaciones_forma(
            _encabezado(deps, lote, sesion), observaciones
        )
        return _respuesta_xlsx(contenido, f"observaciones_lote_{lote.identidad.numero_lote}.xlsx")

    @app.post("/lotes-por-validar/validar", response_model=None)
    async def validar_lotes(request: Request, lote_ids: list[int] = Form(...)) -> RedirectResponse:
        requerir_sesion_activa(request)
        listo_en = datetime.now() + timedelta(
            seconds=configuracion.validacion_segundo_plano_segundos
        )
        for lote_id in lote_ids:
            lote = deps.almacenamiento.obtener(lote_id)
            if lote is not None and lote.estado == "REGISTRADO":
                deps.almacenamiento.marcar_validando(lote_id, listo_en)
        return RedirectResponse("/lotes-por-validar", status_code=303)

    @app.get("/lotes-por-validar/{lote_id}/error-validacion.xlsx", response_model=None)
    async def error_validacion_xlsx(request: Request, lote_id: int) -> Response | PlainTextResponse:
        sesion = requerir_sesion_activa(request)
        lote = deps.almacenamiento.obtener(lote_id)
        if lote is None:
            return PlainTextResponse("Lote no encontrado.", status_code=404)
        filas = deps.almacenamiento.observaciones_de(lote_id, "DETALLADA")
        observaciones = [
            ObservacionDetallada(
                f["tabla"],
                f["numero_linea"],
                f["campo_clave"],
                f["campo"],
                f["valor_observado"],
                f["codigo_error"],
                f["descripcion"],
            )
            for f in filas
        ]
        contenido = generar_reporte_validacion_detallada(
            _encabezado(deps, lote, sesion), observaciones
        )
        return _respuesta_xlsx(
            contenido, f"error_validacion_lote_{lote.identidad.numero_lote}.xlsx"
        )

    @app.post("/lotes-por-validar/{lote_id}/eliminar", response_model=None)
    async def eliminar_por_validar(request: Request, lote_id: int) -> RedirectResponse:
        sesion = requerir_sesion_activa(request)
        deps.almacenamiento.eliminar(lote_id, sesion.usuario)
        return RedirectResponse("/lotes-por-validar", status_code=303)


def _respuesta_xlsx(contenido: bytes, nombre_archivo: str) -> Response:
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


def _registrar_lotes_por_enviar(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasLotes,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    @app.get("/lotes-por-enviar", response_class=HTMLResponse)
    async def lotes_por_enviar(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        lotes = _filtrar(deps.almacenamiento.listar_por_enviar(), request)
        contexto = {**contexto_base(sesion), "lotes": lotes}
        return plantillas.TemplateResponse(request, "lotes_por_enviar.html", contexto)

    @app.get("/lotes-por-enviar/{lote_id}/detalle", response_class=HTMLResponse)
    async def detalle_por_enviar(request: Request, lote_id: int) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        lote = deps.almacenamiento.obtener(lote_id)
        archivos = deps.almacenamiento.archivos_de(lote_id) if lote else []
        contexto = {
            **contexto_base(sesion),
            "lote": lote,
            "archivos": archivos,
            "volver": "/lotes-por-enviar",
        }
        return plantillas.TemplateResponse(request, "detalle_lote.html", contexto)

    @app.get("/lotes-por-enviar/{lote_id}/descargar", response_model=None)
    async def descargar_s01(request: Request, lote_id: int) -> Response | PlainTextResponse:
        requerir_sesion_activa(request)
        lote = deps.almacenamiento.obtener(lote_id)
        contenido = deps.almacenamiento.contenido_s01(lote_id)
        if lote is None or contenido is None or lote.nombre_s01 is None:
            return PlainTextResponse("Lote no encontrado o aun no validado.", status_code=404)
        return Response(
            content=contenido,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{lote.nombre_s01}"'},
        )

    @app.post("/lotes-por-enviar/enviar", response_model=None)
    async def enviar_lotes(
        request: Request, lote_ids: list[int] = Form(...)
    ) -> RedirectResponse | Response:
        sesion = requerir_sesion_activa(request)
        lotes = [deps.almacenamiento.obtener(lote_id) for lote_id in lote_ids]
        invalido = next(
            (lote for lote in lotes if lote is not None and lote.estado != "VALIDADO"), None
        )
        if invalido is not None:
            motivo = (
                f"El lote {invalido.identidad.numero_lote!r} ya fue enviado o no esta validado."
            )
            contenido = generar_reporte_clave_valor(_encabezado(deps, invalido, sesion), motivo)
            return _respuesta_xlsx(
                contenido, f"error_clave_valor_lote_{invalido.identidad.numero_lote}.xlsx"
            )
        for lote_id in lote_ids:
            deps.almacenamiento.marcar_enviado(lote_id)
        return RedirectResponse("/lotes-por-enviar", status_code=303)


def _registrar_lotes_solo_consulta(
    app: FastAPI,
    plantillas: Jinja2Templates,
    deps: DependenciasLotes,
    requerir_sesion_activa: RequerirSesionActiva,
    contexto_base: ContextoBase,
) -> None:
    @app.get("/lotes-enviados", response_class=HTMLResponse)
    async def lotes_enviados(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        lotes = _filtrar(deps.almacenamiento.listar_enviados(), request)
        contexto = {**contexto_base(sesion), "lotes": lotes}
        return plantillas.TemplateResponse(request, "lotes_enviados.html", contexto)

    @app.get("/lotes-eliminados", response_class=HTMLResponse)
    async def lotes_eliminados(request: Request) -> HTMLResponse:
        sesion = requerir_sesion_activa(request)
        lotes = _filtrar(deps.almacenamiento.listar_eliminados(), request)
        contexto = {**contexto_base(sesion), "lotes": lotes}
        return plantillas.TemplateResponse(request, "lotes_eliminados.html", contexto)
