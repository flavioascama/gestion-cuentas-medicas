"""Punto de entrada de la API (AD-05: interfaz HTTP descrita con OpenAPI).

Ejecutar con: uvicorn app.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.compartido.configuracion import obtener_configuracion
from app.dominio.orquestacion.errores import ErrorContinuidadEstados, ErrorTransicionNoDefinida
from app.infraestructura.observabilidad.registro import configurar_registro

# Se configura el registro antes de importar cualquier modulo de la app: aunque
# obtener_registrador() ya no depende del orden de import (ver registro.py),
# se mantiene este orden como buena practica adicional.
configurar_registro(obtener_configuracion().nivel_log)

from app.api.mensajes_transicion import mensaje_operacion_no_disponible  # noqa: E402
from app.api.mensajes_validacion import mensaje_validacion  # noqa: E402
from app.api.middleware_correlacion import middleware_correlacion  # noqa: E402
from app.api.rutas_acreditacion import router as router_acreditacion  # noqa: E402
from app.api.rutas_administracion import router as router_administracion  # noqa: E402
from app.api.rutas_atenciones_cargadas import (  # noqa: E402
    router as router_atenciones_cargadas,
)
from app.api.rutas_atenciones_hospitalarias import (  # noqa: E402
    router as router_atenciones_hospitalarias,
)
from app.api.rutas_auditoria import router as router_auditoria  # noqa: E402
from app.api.rutas_auth import router as router_auth  # noqa: E402
from app.api.rutas_avisos import router as router_avisos  # noqa: E402
from app.api.rutas_carta_garantia import router as router_carta_garantia  # noqa: E402
from app.api.rutas_cierre import router as router_cierre  # noqa: E402
from app.api.rutas_cierre import router_anulaciones  # noqa: E402
from app.api.rutas_comprobante import router as router_comprobante  # noqa: E402
from app.api.rutas_comunicaciones import router as router_comunicaciones  # noqa: E402
from app.api.rutas_contingencia import router as router_contingencia  # noqa: E402
from app.api.rutas_contingencia import router_cuentas as router_contingencia_cuentas  # noqa: E402
from app.api.rutas_contingencia import router_lotes as router_contingencia_lotes  # noqa: E402
from app.api.rutas_correos import router as router_correos  # noqa: E402
from app.api.rutas_cpms import router as router_cpms  # noqa: E402
from app.api.rutas_cuentas import router as router_cuentas  # noqa: E402
from app.api.rutas_cuentas import router_iafas  # noqa: E402
from app.api.rutas_farmacia import router as router_farmacia  # noqa: E402
from app.api.rutas_liquidacion import router as router_liquidacion  # noqa: E402
from app.api.rutas_lotes import router as router_lotes  # noqa: E402
from app.api.rutas_observaciones import router as router_observaciones  # noqa: E402
from app.api.rutas_observaciones import router_item as router_observaciones_item  # noqa: E402
from app.api.rutas_orquestacion import router as router_orquestacion  # noqa: E402
from app.api.rutas_parametros import router as router_parametros  # noqa: E402
from app.api.rutas_plataformas import router as router_plataformas  # noqa: E402
from app.api.rutas_plazos import router as router_plazos  # noqa: E402
from app.api.rutas_respuestas_correo import (  # noqa: E402
    router as router_respuestas_correo,
)
from app.api.rutas_robot import router as router_robot  # noqa: E402
from app.api.rutas_salud import router as router_salud  # noqa: E402
from app.api.rutas_trabajos import router as router_trabajos  # noqa: E402
from app.api.rutas_trazabilidad import router as router_trazabilidad  # noqa: E402
from app.api.rutas_trazabilidad import router_historial_lote, router_indicadores  # noqa: E402
from app.api.rutas_usuarios import router as router_usuarios  # noqa: E402
from app.compartido.errores import ErrorAplicacion  # noqa: E402

app = FastAPI(
    title="Sistema de gestion de cuentas medicas",
    description=(
        "Integracion con el ecosistema regulatorio SUSALUD (OE1), motor de "
        "orquestacion del ciclo de cuentas medicas (OE2) y trazabilidad con panel "
        "de control gerencial (OE3)."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=obtener_configuracion().lista_origenes_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(middleware_correlacion)
app.include_router(router_salud)
app.include_router(router_auth)
app.include_router(router_avisos)
app.include_router(router_usuarios)
app.include_router(router_atenciones_hospitalarias)
app.include_router(router_cuentas)
app.include_router(router_acreditacion)
app.include_router(router_iafas)
app.include_router(router_cpms)
app.include_router(router_lotes)
app.include_router(router_observaciones)
app.include_router(router_observaciones_item)
app.include_router(router_comunicaciones)
app.include_router(router_correos)
app.include_router(router_respuestas_correo)
app.include_router(router_auditoria)
app.include_router(router_carta_garantia)
app.include_router(router_farmacia)
app.include_router(router_comprobante)
app.include_router(router_parametros)
app.include_router(router_liquidacion)
app.include_router(router_cierre)
app.include_router(router_orquestacion)
app.include_router(router_plazos)
app.include_router(router_anulaciones)
app.include_router(router_contingencia)
app.include_router(router_contingencia_cuentas)
app.include_router(router_contingencia_lotes)
app.include_router(router_plataformas)
app.include_router(router_trabajos)
app.include_router(router_trazabilidad)
app.include_router(router_indicadores)
app.include_router(router_historial_lote)
app.include_router(router_administracion)
app.include_router(router_atenciones_cargadas)
app.include_router(router_robot)


@app.exception_handler(RequestValidationError)
async def manejador_validacion(_solicitud: Request, error: RequestValidationError) -> JSONResponse:
    """Un dato rechazado por su forma se responde con el formato de error de la aplicación."""
    rechazo = ErrorAplicacion("DATOS_INVALIDOS", mensaje_validacion(error.errors()), 422)
    return JSONResponse(status_code=rechazo.estado_http, content=rechazo.cuerpo_respuesta())


@app.exception_handler(ErrorAplicacion)
async def manejador_error_aplicacion(_solicitud: Request, error: ErrorAplicacion) -> JSONResponse:
    return JSONResponse(status_code=error.estado_http, content=error.cuerpo_respuesta())


@app.exception_handler(ErrorTransicionNoDefinida)
async def manejador_transicion_no_definida(
    _solicitud: Request, error: ErrorTransicionNoDefinida
) -> JSONResponse:
    """RF-08 y Tabla 69: un evento con un estado o una transicion fuera de la
    maquina de estados se rechaza como conflicto, no como falla interna."""
    conflicto = ErrorAplicacion(
        "TRANSICION_NO_DEFINIDA", mensaje_operacion_no_disponible(error, ultimo=False), 409
    )
    return JSONResponse(status_code=conflicto.estado_http, content=conflicto.cuerpo_respuesta())


@app.exception_handler(ErrorContinuidadEstados)
async def manejador_continuidad_estados(
    _solicitud: Request, error: ErrorContinuidadEstados
) -> JSONResponse:
    """Tabla 69 ("continuidad"): un evento que no parte del ultimo estado
    registrado se rechaza como conflicto, no como falla interna."""
    conflicto = ErrorAplicacion(
        "CONTINUIDAD_ESTADOS", mensaje_operacion_no_disponible(error, ultimo=True), 409
    )
    return JSONResponse(status_code=conflicto.estado_http, content=conflicto.cuerpo_respuesta())
