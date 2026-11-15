"""Simulador ACREDITA SALUD (Seccion 9.1): arma la aplicacion FastAPI con
todas las pantallas del alcance, la latencia artificial y el modo de
falla inducida."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.almacenamiento import Acreditacion, Almacenamiento, CartaGarantia
from app.captcha import GestorCaptcha
from app.configuracion import configuracion
from app.datos import RepositorioDatos
from app.documento import generar_pdf_solicitud
from app.estado_falla import EstadoFalla
from app.excel import generar_excel_historial, leer_documentos_carga_masiva
from app.presentacion import (
    campos_estructurados_cobertura,
    condicion_cobertura,
    datos_copago,
    detalle_cobertura,
)
from app.sesion import NOMBRE_COOKIE, ErrorSesionInvalida, GestorSesiones, Sesion

_RAIZ = Path(__file__).resolve().parent.parent
plantillas = Jinja2Templates(directory=str(_RAIZ / "plantillas"))


def _sembrar_cartas_garantia(repositorio: RepositorioDatos, almacenamiento: Almacenamiento) -> None:
    candidatos = [a for a in repositorio.todos() if a.estado_afiliacion == "ACTIVO"][:5]
    cartas = [
        CartaGarantia(
            numero_carta=f"CG{indice + 1:06d}",
            tipo_documento=a.tipo_documento,
            numero_documento=a.numero_documento,
            nombre_asegurado=a.nombre_completo,
            monto=round(500.0 + indice * 137.5, 2),
            estado="VIGENTE" if indice % 3 != 0 else "VENCIDA",
            fecha_emision="2026-06-01",
            fecha_vencimiento="2026-12-01",
            motivo="Atencion de mayor complejidad (ficticio)",
        )
        for indice, a in enumerate(candidatos)
    ]
    almacenamiento.sembrar_cartas_garantia_si_vacio(cartas)


def construir_app(repositorio: RepositorioDatos, almacenamiento: Almacenamiento) -> FastAPI:
    app = FastAPI(title="Simulador ACREDITA SALUD")
    gestor_sesiones = GestorSesiones(configuracion.sesion_expiracion_minutos)
    gestor_captcha = GestorCaptcha()
    estado_falla = EstadoFalla(configuracion.modo_falla_inicial)
    _sembrar_cartas_garantia(repositorio, almacenamiento)

    def requerir_sesion(request: Request) -> Sesion:
        if estado_falla.modo == "expiracion_sesion":
            raise ErrorSesionInvalida()
        sesion = gestor_sesiones.validar(request.cookies.get(NOMBRE_COOKIE))
        if sesion is None:
            raise ErrorSesionInvalida()
        return sesion

    def contexto_base(sesion: Sesion) -> dict[str, object]:
        return {"usuario": sesion.usuario, "perfil_carga_masiva": configuracion.perfil_carga_masiva}

    @app.exception_handler(ErrorSesionInvalida)
    async def manejar_sesion_invalida(
        request: Request, exc: ErrorSesionInvalida
    ) -> RedirectResponse:
        return RedirectResponse("/ingreso", status_code=303)

    @app.middleware("http")
    async def middleware_simulacion(request: Request, call_next):  # type: ignore[no-untyped-def]
        if configuracion.latencia_artificial_ms > 0:
            await asyncio.sleep(configuracion.latencia_artificial_ms / 1000)
        if estado_falla.modo == "caida_servicio" and not request.url.path.startswith("/admin"):
            return PlainTextResponse(
                "Servicio no disponible (falla inducida, Seccion 9.1).", status_code=503
            )
        return await call_next(request)  # type: ignore[no-any-return]

    # --- ingreso -------------------------------------------------------

    @app.get("/", response_model=None)
    async def raiz(request: Request) -> RedirectResponse:
        sesion = gestor_sesiones.validar(request.cookies.get(NOMBRE_COOKIE))
        return RedirectResponse("/menu" if sesion else "/ingreso")

    @app.get("/ingreso", response_class=HTMLResponse)
    async def formulario_ingreso(request: Request) -> HTMLResponse:
        captcha = gestor_captcha.generar()
        return plantillas.TemplateResponse(
            request, "ingreso.html", {"usuario": None, "captcha_id": captcha.id}
        )

    @app.get("/captcha/{captcha_id}.png", response_model=None)
    async def imagen_captcha(captcha_id: str) -> Response | PlainTextResponse:
        imagen = gestor_captcha.imagen_png(captcha_id)
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
        # Seccion 5.1 del manual: un mensaje distinto por cada validacion
        # (usuario, contrasena, CAPTCHA), en ese orden -- el mismo orden en
        # que aparecen los campos en la pantalla de ingreso. `tipo_error`
        # selecciona cual de los tres `data-testid` separados se muestra
        # (configuracion/selectores/acredita_salud.yaml): el robot de
        # sesion asistida (Fase 15) necesita distinguirlos, no solo leer
        # un mensaje generico.
        tipo_error = None
        if usuario != configuracion.usuario:
            tipo_error = "usuario"
        elif clave != configuracion.clave:
            tipo_error = "clave"
        elif not gestor_captcha.verificar_y_consumir(captcha_id, respuesta_captcha):
            tipo_error = "captcha"

        if tipo_error is not None:
            nuevo_captcha = gestor_captcha.generar()
            return plantillas.TemplateResponse(
                request,
                "ingreso.html",
                {"usuario": None, "captcha_id": nuevo_captcha.id, "tipo_error": tipo_error},
                status_code=401,
            )

        sesion = gestor_sesiones.iniciar(usuario)
        respuesta = RedirectResponse("/menu", status_code=303)
        respuesta.set_cookie(NOMBRE_COOKIE, sesion.token, httponly=True, samesite="lax")
        return respuesta

    @app.post("/salir", response_model=None)
    async def salir(request: Request) -> RedirectResponse:
        token = request.cookies.get(NOMBRE_COOKIE)
        if token:
            gestor_sesiones.cerrar(token)
        respuesta = RedirectResponse("/ingreso", status_code=303)
        respuesta.delete_cookie(NOMBRE_COOKIE)
        return respuesta

    # --- menu ------------------------------------------------------------

    @app.get("/menu", response_class=HTMLResponse)
    async def menu(request: Request) -> HTMLResponse:
        sesion = requerir_sesion(request)
        return plantillas.TemplateResponse(request, "menu.html", contexto_base(sesion))

    # --- consulta RAAUS --------------------------------------------------

    @app.get("/acreditacion/raaus", response_class=HTMLResponse)
    async def formulario_raaus(request: Request) -> HTMLResponse:
        sesion = requerir_sesion(request)
        return plantillas.TemplateResponse(request, "raaus.html", contexto_base(sesion))

    @app.post("/acreditacion/raaus", response_class=HTMLResponse)
    async def procesar_raaus(
        request: Request, tipo_documento: str = Form(...), numero_documento: str = Form(...)
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        asegurado = None
        if estado_falla.modo != "respuesta_vacia":
            asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
        contexto = {
            **contexto_base(sesion),
            "buscado": True,
            "numero_documento": numero_documento,
            "asegurado": asegurado,
            "nombre_iafas": repositorio.nombre_iafas(asegurado.iafas_codigo) if asegurado else None,
        }
        return plantillas.TemplateResponse(request, "raaus.html", contexto)

    # --- consulta directa por IAFAS --------------------------------------

    @app.get("/acreditacion/iafas", response_class=HTMLResponse)
    async def formulario_iafas(
        request: Request, tipo_documento: str | None = None, numero_documento: str | None = None
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        contexto = {
            **contexto_base(sesion),
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
        }
        return plantillas.TemplateResponse(request, "iafas.html", contexto)

    @app.post("/acreditacion/iafas", response_class=HTMLResponse)
    async def procesar_iafas(
        request: Request, tipo_documento: str = Form(...), numero_documento: str = Form(...)
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        asegurado = None
        if estado_falla.modo != "respuesta_vacia":
            asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
        contexto = {
            **contexto_base(sesion),
            "buscado": True,
            "tipo_documento": tipo_documento,
            "numero_documento": numero_documento,
            "asegurado": asegurado,
            "nombre_iafas": repositorio.nombre_iafas(asegurado.iafas_codigo) if asegurado else None,
            "detalle": detalle_cobertura(asegurado) if asegurado else [],
            "campos": campos_estructurados_cobertura(asegurado) if asegurado else None,
        }
        return plantillas.TemplateResponse(request, "iafas.html", contexto)

    # --- acreditacion: evaluacion y generacion ----------------------------

    @app.get("/acreditacion/evaluar", response_model=None)
    async def evaluar(
        request: Request, tipo_documento: str, numero_documento: str
    ) -> HTMLResponse | PlainTextResponse:
        sesion = requerir_sesion(request)
        asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
        if asegurado is None:
            return PlainTextResponse("Asegurado no encontrado.", status_code=404)
        contexto = {
            **contexto_base(sesion),
            "asegurado": asegurado,
            "nombre_iafas": repositorio.nombre_iafas(asegurado.iafas_codigo),
            "condicion_cobertura": condicion_cobertura(asegurado),
            "copago": datos_copago(asegurado),
        }
        return plantillas.TemplateResponse(request, "evaluar.html", contexto)

    @app.post("/acreditacion/generar", response_model=None)
    async def generar_autorizacion(
        request: Request, tipo_documento: str = Form(...), numero_documento: str = Form(...)
    ) -> RedirectResponse | PlainTextResponse:
        requerir_sesion(request)
        asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
        if asegurado is None:
            return PlainTextResponse("Asegurado no encontrado.", status_code=404)

        copago = datos_copago(asegurado)
        codigo = f"AUT{almacenamiento.contar_acreditaciones() + 1:07d}"
        almacenamiento.registrar_acreditacion(
            Acreditacion(
                codigo_autorizacion=codigo,
                tipo_documento=asegurado.tipo_documento,
                numero_documento=asegurado.numero_documento,
                nombre_asegurado=asegurado.nombre_completo,
                iafas_codigo=asegurado.iafas_codigo,
                ipress_codigo=configuracion.ipress_codigo,
                condicion_cobertura=condicion_cobertura(asegurado),
                tipo_copago=copago.tipo,
                monto_copago_fijo=copago.monto_fijo,
                porcentaje_coaseguro=copago.porcentaje_coaseguro,
                generado_en=datetime.now().isoformat(),
            )
        )
        return RedirectResponse(f"/acreditacion/{codigo}/documento", status_code=303)

    @app.get("/acreditacion/{codigo}/documento", response_model=None)
    async def ver_documento(
        request: Request, codigo: str, reimpresion: bool = False
    ) -> HTMLResponse | PlainTextResponse:
        sesion = requerir_sesion(request)
        acreditacion = almacenamiento.obtener_acreditacion(codigo)
        if acreditacion is None:
            return PlainTextResponse("Acreditación no encontrada.", status_code=404)
        contexto = {
            **contexto_base(sesion),
            "acreditacion": acreditacion,
            "nombre_iafas": repositorio.nombre_iafas(acreditacion.iafas_codigo),
            "reimpresion": reimpresion,
        }
        return plantillas.TemplateResponse(request, "documento.html", contexto)

    @app.get("/acreditacion/{codigo}/documento.pdf", response_model=None)
    async def descargar_documento_pdf(
        request: Request, codigo: str, reimpresion: bool = False
    ) -> Response | PlainTextResponse:
        requerir_sesion(request)
        acreditacion = almacenamiento.obtener_acreditacion(codigo)
        if acreditacion is None:
            return PlainTextResponse("Acreditación no encontrada.", status_code=404)
        contenido = generar_pdf_solicitud(acreditacion, repositorio, reimpresion)
        return Response(
            content=contenido,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{codigo}.pdf"'},
        )

    # --- atenciones accidentales -----------------------------------------

    @app.get("/atencion-accidental", response_class=HTMLResponse)
    async def formulario_siniestro(request: Request) -> HTMLResponse:
        sesion = requerir_sesion(request)
        return plantillas.TemplateResponse(
            request, "atencion_accidental.html", contexto_base(sesion)
        )

    @app.post("/atencion-accidental", response_class=HTMLResponse)
    async def procesar_siniestro(
        request: Request,
        tipo_documento: str = Form(...),
        numero_documento: str = Form(...),
        fecha_siniestro: date = Form(...),
        descripcion: str = Form(...),
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        almacenamiento.registrar_siniestro(
            tipo_documento, numero_documento, fecha_siniestro.isoformat(), descripcion
        )
        contexto = {**contexto_base(sesion), "registrado": True}
        return plantillas.TemplateResponse(request, "atencion_accidental.html", contexto)

    # --- derivacion entre IPRESS -------------------------------------------

    @app.get("/derivacion", response_class=HTMLResponse)
    async def formulario_derivacion(request: Request) -> HTMLResponse:
        sesion = requerir_sesion(request)
        return plantillas.TemplateResponse(request, "derivacion.html", contexto_base(sesion))

    @app.post("/derivacion", response_class=HTMLResponse)
    async def procesar_derivacion(
        request: Request,
        tipo_documento: str = Form(...),
        numero_documento: str = Form(...),
        ipress_origen: str = Form(...),
        ipress_destino: str = Form(...),
        motivo: str = Form(...),
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
        if asegurado is None:
            contexto = {**contexto_base(sesion), "error": "Asegurado no encontrado."}
        else:
            # Seccion 9.1: 'cuando existe convenio con la IAFAS'. Todas las
            # IAFAS de este simulador son sinteticas y se tratan como
            # conveniadas (no hay catalogo real de convenios que consultar).
            almacenamiento.registrar_derivacion(
                tipo_documento, numero_documento, ipress_origen, ipress_destino, motivo
            )
            contexto = {**contexto_base(sesion), "registrado": True}
        return plantillas.TemplateResponse(request, "derivacion.html", contexto)

    # --- cartas de garantia --------------------------------------------------

    @app.get("/cartas-garantia", response_class=HTMLResponse)
    async def buscar_cartas_garantia(
        request: Request, numero_documento: str | None = None, numero_carta: str | None = None
    ) -> HTMLResponse:
        sesion = requerir_sesion(request)
        cartas = almacenamiento.buscar_cartas_garantia(
            numero_documento or None, numero_carta or None
        )
        contexto = {
            **contexto_base(sesion),
            "numero_documento": numero_documento,
            "numero_carta": numero_carta,
            "cartas": cartas,
        }
        return plantillas.TemplateResponse(request, "cartas_garantia.html", contexto)

    # --- historial ------------------------------------------------------------

    def _filtros_historial(
        request: Request,
    ) -> tuple[str | None, date | None, date | None, str | None]:
        parametros = request.query_params
        ipress_codigo = parametros.get("ipress_codigo") or None
        desde = date.fromisoformat(parametros["desde"]) if parametros.get("desde") else None
        hasta = date.fromisoformat(parametros["hasta"]) if parametros.get("hasta") else None
        codigo_autorizacion = parametros.get("codigo_autorizacion") or None
        return ipress_codigo, desde, hasta, codigo_autorizacion

    @app.get("/historial", response_class=HTMLResponse)
    async def historial(request: Request) -> HTMLResponse:
        sesion = requerir_sesion(request)
        ipress_codigo, desde, hasta, codigo_autorizacion = _filtros_historial(request)
        acreditaciones = almacenamiento.buscar_acreditaciones(
            ipress_codigo, desde, hasta, codigo_autorizacion
        )
        contexto = {
            **contexto_base(sesion),
            "ipress_codigo": ipress_codigo,
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
            "codigo_autorizacion": codigo_autorizacion,
            "acreditaciones": acreditaciones,
            "cadena_consulta": urlencode(dict(request.query_params)),
        }
        return plantillas.TemplateResponse(request, "historial.html", contexto)

    @app.get("/historial/exportar.xlsx", response_model=None)
    async def exportar_historial(request: Request) -> StreamingResponse:
        requerir_sesion(request)
        ipress_codigo, desde, hasta, codigo_autorizacion = _filtros_historial(request)
        acreditaciones = almacenamiento.buscar_acreditaciones(
            ipress_codigo, desde, hasta, codigo_autorizacion
        )
        contenido = generar_excel_historial(acreditaciones)
        return StreamingResponse(
            iter([contenido]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="historial_acreditaciones.xlsx"'},
        )

    # --- carga masiva -------------------------------------------------------

    @app.get("/carga-masiva", response_model=None)
    async def formulario_carga_masiva(request: Request) -> HTMLResponse | PlainTextResponse:
        sesion = requerir_sesion(request)
        if not configuracion.perfil_carga_masiva:
            return PlainTextResponse("Perfil de carga masiva no habilitado.", status_code=403)
        return plantillas.TemplateResponse(request, "carga_masiva.html", contexto_base(sesion))

    @app.post("/carga-masiva", response_model=None)
    async def procesar_carga_masiva(
        request: Request, archivo: UploadFile
    ) -> HTMLResponse | PlainTextResponse:
        sesion = requerir_sesion(request)
        if not configuracion.perfil_carga_masiva:
            return PlainTextResponse("Perfil de carga masiva no habilitado.", status_code=403)
        assert isinstance(archivo, StarletteUploadFile)
        contenido = await archivo.read()
        documentos = leer_documentos_carga_masiva(contenido)

        resultados = []
        for tipo_documento, numero_documento in documentos:
            asegurado = repositorio.buscar_por_documento(tipo_documento, numero_documento)
            if asegurado is None:
                resultados.append(
                    {
                        "tipo_documento": tipo_documento,
                        "numero_documento": numero_documento,
                        "exito": False,
                        "mensaje": "No encontrado",
                        "codigo_autorizacion": None,
                    }
                )
                continue
            copago = datos_copago(asegurado)
            codigo = f"AUT{almacenamiento.contar_acreditaciones() + 1:07d}"
            almacenamiento.registrar_acreditacion(
                Acreditacion(
                    codigo_autorizacion=codigo,
                    tipo_documento=asegurado.tipo_documento,
                    numero_documento=asegurado.numero_documento,
                    nombre_asegurado=asegurado.nombre_completo,
                    iafas_codigo=asegurado.iafas_codigo,
                    ipress_codigo=configuracion.ipress_codigo,
                    condicion_cobertura=condicion_cobertura(asegurado),
                    tipo_copago=copago.tipo,
                    monto_copago_fijo=copago.monto_fijo,
                    porcentaje_coaseguro=copago.porcentaje_coaseguro,
                    generado_en=datetime.now().isoformat(),
                )
            )
            resultados.append(
                {
                    "tipo_documento": tipo_documento,
                    "numero_documento": numero_documento,
                    "exito": True,
                    "mensaje": "Acreditado",
                    "codigo_autorizacion": codigo,
                }
            )

        contexto = {**contexto_base(sesion), "resultados": resultados}
        return plantillas.TemplateResponse(request, "carga_masiva.html", contexto)

    # --- administracion (Seccion 9.1: ruta de administracion para forzar falla) --

    @app.post("/admin/falla", response_model=None)
    async def fijar_falla(modo: str = Form(...)) -> PlainTextResponse:
        estado_falla.fijar(modo)
        return PlainTextResponse(f"Modo de falla fijado a {modo!r}.")

    @app.get("/admin/falla", response_model=None)
    async def obtener_falla() -> PlainTextResponse:
        return PlainTextResponse(estado_falla.modo)

    @app.get("/admin/configuracion", response_model=None)
    async def obtener_configuracion_simulador() -> JSONResponse:
        """Seccion 13 (Fase 20): la cabecera de los archivos de evidencia
        exige "la latencia artificial configurada de cada simulador
        durante esa ejecucion" -- expuesta aqui para que las herramientas
        de generacion de evidencia (que corren en otro contenedor, sin
        acceso a las variables de entorno de este proceso) la lean por
        HTTP en vez de asumir un valor fijo."""

        return JSONResponse({"latencia_artificial_ms": configuracion.latencia_artificial_ms})

    @app.get("/admin/captcha/{captcha_id}", response_model=None)
    async def obtener_texto_captcha(captcha_id: str) -> PlainTextResponse:
        """Seccion 8.4: "ruta de administracion que devuelve el texto del
        CAPTCHA vigente solo si SIMULADOR_MODO_PRUEBA=true; la prueba
        actua como el usuario humano llamando a la API del sistema, nunca
        el robot" -- el robot de sesion asistida jamas llama esta ruta."""

        if not configuracion.simulador_modo_prueba:
            return PlainTextResponse("No disponible.", status_code=403)
        texto = gestor_captcha.texto_vigente(captcha_id)
        if texto is None:
            return PlainTextResponse("CAPTCHA no encontrado o vencido.", status_code=404)
        return PlainTextResponse(texto)

    @app.get("/admin/captcha", response_model=None)
    async def obtener_texto_captcha_mas_reciente() -> PlainTextResponse:
        """Fase 20: variante sin id de `/admin/captcha/{captcha_id}` de
        arriba, para una prueba de integracion que actua como "usuario
        humano" (Seccion 8.4) sin abrir un navegador -- nunca conoce el
        `captcha_id` que el robot genero al abrir `/ingreso`, porque ese
        id no se persiste en el backend (solo la imagen)."""

        if not configuracion.simulador_modo_prueba:
            return PlainTextResponse("No disponible.", status_code=403)
        texto = gestor_captcha.texto_del_mas_reciente()
        if texto is None:
            return PlainTextResponse("No hay ningun CAPTCHA vigente.", status_code=404)
        return PlainTextResponse(texto)

    return app


def crear_app_desde_configuracion() -> FastAPI:
    """Punto de entrada perezoso para uvicorn (`--factory`): construir la
    app aqui, y no en una variable de modulo, evita que importar este
    archivo (por ejemplo, desde las pruebas) intente leer
    datos_semilla/asegurados.json antes de tiempo -- el mismo error de
    resolucion eager de rutas que ya paso en la Fase 1 del backend."""

    repositorio = RepositorioDatos(configuracion.datos_semilla / "asegurados.json")
    almacenamiento = Almacenamiento(configuracion.base_datos)
    return construir_app(repositorio, almacenamiento)
