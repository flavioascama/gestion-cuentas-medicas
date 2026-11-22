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
    construir_corregir_liquidacion,
    construir_corregir_pago,
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
from app.api.mensajes_transicion import mensaje_operacion_no_disponible
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.liquidacion.casos_uso import (
    ConciliarPago,
    CorregirLiquidacion,
    ObtenerLiquidacion,
    RegistrarLiquidacion,
)
from app.dominio.liquidacion.correccion_pago import CorregirPago
from app.dominio.liquidacion.errores import (
    ErrorLiquidacionInexistente,
    ErrorLiquidacionNoCorregible,
    ErrorMontoExcedido,
    ErrorPagoNoCorregible,
    ErrorPagoYaConciliado,
)
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["liquidacion"])

_SOLO_TESORERIA = requiere_rol(NombreRol.TESORERIA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)


def _monto_excedido(error: ErrorMontoExcedido) -> ErrorAplicacion:
    return ErrorAplicacion("MONTO_EXCEDIDO", str(error), estado_http=status.HTTP_409_CONFLICT)


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
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    except ErrorMontoExcedido as error:
        raise _monto_excedido(error) from error
    return RespuestaLiquidacionRegistrada.desde_valor(resultado)


@router.put("/liquidacion", response_model=LiquidacionRespuesta)
async def corregir_liquidacion(
    cuenta_id: int,
    solicitud: SolicitudRegistroLiquidacion,
    caso_uso: CorregirLiquidacion = Depends(construir_corregir_liquidacion),
    actor: CargaSesion = Depends(_SOLO_TESORERIA),
) -> LiquidacionRespuesta:
    """Corrige el monto liquidado mientras la cuenta siga en el estado en que
    quedo al liquidarse y sin pago registrado."""
    try:
        liquidacion = await caso_uso.ejecutar(
            cuenta_id, solicitud.monto_liquidado, actor.nombre_usuario
        )
    except ErrorLiquidacionInexistente as error:
        raise ErrorAplicacion(
            "LIQUIDACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorLiquidacionNoCorregible as error:
        raise ErrorAplicacion(
            "LIQUIDACION_NO_CORREGIBLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorMontoExcedido as error:
        raise _monto_excedido(error) from error
    return LiquidacionRespuesta.desde_valor(liquidacion, corregible=True)


@router.get("/liquidacion", response_model=LiquidacionRespuesta | None)
async def obtener_liquidacion(
    cuenta_id: int,
    caso_uso: ObtenerLiquidacion = Depends(construir_obtener_liquidacion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> LiquidacionRespuesta | None:
    liquidacion = await caso_uso.ejecutar(cuenta_id)
    if liquidacion is None:
        return None
    return LiquidacionRespuesta.desde_valor(
        liquidacion,
        corregible=await caso_uso.corregible(liquidacion),
        pago_corregible=await caso_uso.pago_corregible(liquidacion),
    )


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
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    except ErrorMontoExcedido as error:
        raise _monto_excedido(error) from error
    return RespuestaConciliacion.desde_valor(resultado)


@router.put("/pago", response_model=LiquidacionRespuesta)
async def corregir_pago(
    cuenta_id: int,
    solicitud: SolicitudConciliacionPago,
    caso_uso: CorregirPago = Depends(construir_corregir_pago),
    actor: CargaSesion = Depends(_SOLO_TESORERIA),
) -> LiquidacionRespuesta:
    """Corrige lo pagado que registro una persona mientras la cuenta no este
    Cerrada ni Anulada; queda en el historial."""
    try:
        liquidacion = await caso_uso.ejecutar(
            cuenta_id, solicitud.monto_pagado, actor.nombre_usuario
        )
    except ErrorLiquidacionInexistente as error:
        raise ErrorAplicacion(
            "LIQUIDACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorPagoNoCorregible as error:
        raise ErrorAplicacion(
            "PAGO_NO_CORREGIBLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorMontoExcedido as error:
        raise _monto_excedido(error) from error
    return LiquidacionRespuesta.desde_valor(liquidacion, pago_corregible=True)
