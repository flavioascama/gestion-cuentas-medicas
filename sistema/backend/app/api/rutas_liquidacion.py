"""CU-12 (RF-08, RF-12, RF-16): "la tesoreria registra el monto
liquidado... y, al recibir el pago, registra el monto y su
correspondencia con la liquidacion" (Tabla 51) -- ambas operaciones son
exclusivas de tesoreria; la lectura, de cualquier rol involucrado en el
ciclo (Fase 28)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_liquidacion import (
    construir_conciliar_pago,
    construir_obtener_liquidacion,
    construir_registrar_liquidacion,
)
from app.api.esquemas_liquidacion import (
    LiquidacionRespuesta,
    RespuestaConciliacion,
    RespuestaLiquidacionRegistrada,
    SolicitudConciliacionPago,
    SolicitudRegistroLiquidacion,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.liquidacion.casos_uso import (
    ConciliarPago,
    ObtenerLiquidacion,
    RegistrarLiquidacion,
)
from app.dominio.liquidacion.errores import ErrorLiquidacionInexistente, ErrorPagoYaConciliado
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["liquidacion"])

_SOLO_TESORERIA = requiere_rol(NombreRol.TESORERIA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)


@router.post(
    "/liquidacion",
    response_model=RespuestaLiquidacionRegistrada,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_liquidacion(
    cuenta_id: int,
    solicitud: SolicitudRegistroLiquidacion,
    caso_uso: RegistrarLiquidacion = Depends(construir_registrar_liquidacion),
    actor: CargaSesion = Depends(_SOLO_TESORERIA),
) -> RespuestaLiquidacionRegistrada:
    try:
        resultado = await caso_uso.ejecutar(
            cuenta_id, solicitud.monto_liquidado, actor.nombre_usuario
        )
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaLiquidacionRegistrada.desde_valor(resultado)


@router.get("/liquidacion", response_model=LiquidacionRespuesta | None)
async def obtener_liquidacion(
    cuenta_id: int,
    caso_uso: ObtenerLiquidacion = Depends(construir_obtener_liquidacion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> LiquidacionRespuesta | None:
    liquidacion = await caso_uso.ejecutar(cuenta_id)
    return None if liquidacion is None else LiquidacionRespuesta.desde_valor(liquidacion)


@router.post("/pago", response_model=RespuestaConciliacion, status_code=status.HTTP_201_CREATED)
async def conciliar_pago(
    cuenta_id: int,
    solicitud: SolicitudConciliacionPago,
    caso_uso: ConciliarPago = Depends(construir_conciliar_pago),
    actor: CargaSesion = Depends(_SOLO_TESORERIA),
) -> RespuestaConciliacion:
    try:
        resultado = await caso_uso.ejecutar(cuenta_id, solicitud.monto_pagado, actor.nombre_usuario)
    except ErrorLiquidacionInexistente as error:
        raise ErrorAplicacion(
            "LIQUIDACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorPagoYaConciliado as error:
        raise ErrorAplicacion(
            "PAGO_YA_CONCILIADO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaConciliacion.desde_valor(resultado)
