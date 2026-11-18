"""POST /auth/sesion (Seccion 10.1, CU-17), publica. DELETE /auth/sesion
(Seccion 11, Fase 18) y PUT /auth/clave (2026-11-18), autenticadas: son
las dos unicas operaciones que admite quien aun debe cambiar su clave
temporal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import (
    autenticar_sesion,
    construir_cambiar_clave,
    construir_cerrar_sesion,
    construir_iniciar_sesion,
)
from app.api.esquemas_acceso import (
    RespuestaInicioSesion,
    SolicitudCambioClave,
    SolicitudInicioSesion,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.cambio_clave import CambiarClavePropia
from app.dominio.acceso.casos_uso import CerrarSesion, IniciarSesion
from app.dominio.acceso.errores import (
    ClaveActualIncorrectaError,
    ClaveDebilError,
    ClaveRepetidaError,
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    ErrorAcceso,
)
from app.dominio.acceso.puertos import CargaSesion
from app.infraestructura.observabilidad.registro import obtener_registrador

router = APIRouter(prefix="/auth", tags=["auth"])
_registrador = obtener_registrador("api.auth")


@router.post("/sesion", response_model=RespuestaInicioSesion)
async def iniciar_sesion(
    solicitud: SolicitudInicioSesion,
    caso_uso: IniciarSesion = Depends(construir_iniciar_sesion),
) -> RespuestaInicioSesion:
    try:
        token = await caso_uso.ejecutar(solicitud.nombre_usuario, solicitud.clave)
    except CuentaBloqueadaError as error:
        # Control C-01 (Seccion 5.2.7): distinto de credenciales invalidas
        # a proposito -- la persona debe saber que debe esperar, no seguir
        # probando claves. 423 Locked es el codigo HTTP que nombra
        # exactamente este caso (RFC 4918).
        _registrador.info(
            "inicio_sesion_bloqueado",
            caso_uso="iniciar_sesion",
            actor=solicitud.nombre_usuario,
        )
        raise ErrorAplicacion("CUENTA_BLOQUEADA", str(error), estado_http=423) from error
    except CredencialesInvalidasError as error:
        _registrador.info(
            "inicio_sesion_rechazado",
            caso_uso="iniciar_sesion",
            actor=solicitud.nombre_usuario,
        )
        raise ErrorAplicacion(
            "CREDENCIALES_INVALIDAS", str(error), estado_http=status.HTTP_401_UNAUTHORIZED
        ) from error

    _registrador.info(
        "inicio_sesion_aceptado", caso_uso="iniciar_sesion", actor=solicitud.nombre_usuario
    )
    return RespuestaInicioSesion(token=token)


@router.delete("/sesion", status_code=status.HTTP_204_NO_CONTENT)
async def cerrar_sesion(
    caso_uso: CerrarSesion = Depends(construir_cerrar_sesion),
    actor: CargaSesion = Depends(autenticar_sesion),
) -> None:
    await caso_uso.ejecutar(actor.nombre_usuario, actor.usuario_id, actor.jti, actor.expira_en)
    _registrador.info("sesion_cerrada", caso_uso="cerrar_sesion", actor=actor.nombre_usuario)


_CODIGOS_CAMBIO_CLAVE: dict[type[ErrorAcceso], str] = {
    ClaveActualIncorrectaError: "CLAVE_ACTUAL_INCORRECTA",
    ClaveRepetidaError: "CLAVE_REPETIDA",
    ClaveDebilError: "CLAVE_DEBIL",
}


@router.put("/clave", response_model=RespuestaInicioSesion)
async def cambiar_clave(
    solicitud: SolicitudCambioClave,
    caso_uso: CambiarClavePropia = Depends(construir_cambiar_clave),
    actor: CargaSesion = Depends(autenticar_sesion),
) -> RespuestaInicioSesion:
    """Devuelve una credencial nueva: la anterior queda revocada."""
    try:
        token = await caso_uso.ejecutar(actor, solicitud.clave_actual, solicitud.clave_nueva)
    except CuentaBloqueadaError as error:
        raise ErrorAplicacion("CUENTA_BLOQUEADA", str(error), estado_http=423) from error
    except (ClaveActualIncorrectaError, ClaveRepetidaError, ClaveDebilError) as error:
        # 400 y no 401: la credencial es valida, lo que falla es el dato.
        raise ErrorAplicacion(
            _CODIGOS_CAMBIO_CLAVE[type(error)],
            str(error),
            estado_http=status.HTTP_400_BAD_REQUEST,
        ) from error
    _registrador.info("clave_cambiada", caso_uso="cambiar_clave", actor=actor.nombre_usuario)
    return RespuestaInicioSesion(token=token)
