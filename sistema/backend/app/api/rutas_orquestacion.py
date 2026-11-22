"""T-05 (Tabla 58, camino de excepcion del TO-BE): consultar por que la
IAFAS rechazo la cuenta y corregirla para su reenvio. Leer el rechazo es
de los mismos roles que leen la cuenta; corregir es del analista, igual
que el resto de las operaciones de facturacion (Tabla 46)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_orquestacion import (
    construir_corregir_cuenta_rechazada,
    construir_obtener_rechazo_cuenta,
)
from app.api.esquemas_orquestacion import (
    RechazoCuentaRespuesta,
    RespuestaCorreccionReenvio,
    SolicitudCorreccionReenvio,
)
from app.api.mensajes_transicion import mensaje_operacion_no_disponible
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.orquestacion.casos_uso import CorregirCuentaRechazada, ObtenerRechazoCuenta
from app.dominio.orquestacion.errores import (
    ErrorComprobanteDesfasado,
    ErrorTransicionNoDefinida,
)

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["orquestacion"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)


@router.get("/rechazo", response_model=RechazoCuentaRespuesta)
async def obtener_rechazo_cuenta(
    cuenta_id: int,
    caso_uso: ObtenerRechazoCuenta = Depends(construir_obtener_rechazo_cuenta),
    _actor: CargaSesion = Depends(_LECTURA),
) -> RechazoCuentaRespuesta:
    rechazo = await caso_uso.ejecutar(cuenta_id)
    if rechazo is None:
        raise ErrorAplicacion(
            "SIN_RECHAZO",
            "Ningún lote de la cuenta fue rechazado por la IAFAS.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return RechazoCuentaRespuesta.desde_valor(rechazo)


@router.post("/correccion-reenvio", response_model=RespuestaCorreccionReenvio)
async def corregir_cuenta_rechazada(
    cuenta_id: int,
    solicitud: SolicitudCorreccionReenvio,
    caso_uso: CorregirCuentaRechazada = Depends(construir_corregir_cuenta_rechazada),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaCorreccionReenvio:
    try:
        estado_nuevo = await caso_uso.ejecutar(
            cuenta_id, solicitud.descripcion_correccion, actor.nombre_usuario
        )
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    except ErrorComprobanteDesfasado as error:
        raise ErrorAplicacion(
            "COMPROBANTE_DESFASADO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaCorreccionReenvio(estado_cuenta=estado_nuevo)
