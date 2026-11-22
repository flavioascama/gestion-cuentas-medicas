"""Seccion 11, 8.4: /plataformas. Las cuatro rutas son solo para analista
(Fase 18) -- el usuario que pulsa "Iniciar sesion" y responde el CAPTCHA."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.api.dependencias import requiere_rol
from app.api.dependencias_plataformas import (
    construir_listar_sesiones_plataforma,
    construir_obtener_sesion_plataforma,
    construir_responder_captcha,
    construir_solicitar_sesion_plataforma,
)
from app.api.esquemas_plataformas import (
    RespuestaSesionSolicitada,
    ResumenSesionPlataformaRespuesta,
    SolicitudRespuestaCaptcha,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.plataformas.casos_uso import (
    ListarSesionesPlataforma,
    ObtenerSesionPlataforma,
    ResponderCaptcha,
    SolicitarSesionPlataforma,
)
from app.dominio.plataformas.puertos import (
    ErrorPlataformaInvalida,
    ErrorSesionNoEncontrada,
    ErrorSesionPlataforma,
)

router = APIRouter(prefix="/plataformas", tags=["plataformas"])
# La sesion asistida la abre quien opera la plataforma: el analista y, para
# validar el lote en TEDEF Web (Tabla 46), tambien el jefe (2026-11-13).
_OPERA_PLATAFORMAS = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)


@router.get("/sesiones", response_model=list[ResumenSesionPlataformaRespuesta])
async def listar_sesiones(
    plataforma: str | None = None,
    caso_uso: ListarSesionesPlataforma = Depends(construir_listar_sesiones_plataforma),
    _actor: CargaSesion = Depends(_OPERA_PLATAFORMAS),
) -> list[ResumenSesionPlataformaRespuesta]:
    sesiones = await caso_uso.ejecutar(plataforma)
    return [ResumenSesionPlataformaRespuesta.desde_valor(s) for s in sesiones]


@router.post(
    "/{plataforma}/sesion",
    response_model=RespuestaSesionSolicitada,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_sesion(
    plataforma: str,
    caso_uso: SolicitarSesionPlataforma = Depends(construir_solicitar_sesion_plataforma),
    actor: CargaSesion = Depends(_OPERA_PLATAFORMAS),
) -> RespuestaSesionSolicitada:
    try:
        sesion_id = await caso_uso.ejecutar(plataforma, actor.nombre_usuario)
    except ErrorPlataformaInvalida as error:
        raise ErrorAplicacion(
            "PLATAFORMA_INVALIDA", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    return RespuestaSesionSolicitada(sesion_id=sesion_id)


@router.get("/sesiones/{sesion_id}/captcha")
async def obtener_captcha(
    sesion_id: int,
    caso_uso: ObtenerSesionPlataforma = Depends(construir_obtener_sesion_plataforma),
    _actor: CargaSesion = Depends(_OPERA_PLATAFORMAS),
) -> Response:
    sesion = await caso_uso.ejecutar(sesion_id)
    if sesion is None or sesion.imagen_captcha is None:
        raise ErrorAplicacion(
            "CAPTCHA_NO_DISPONIBLE",
            "La sesión no tiene un código de verificación pendiente.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return Response(content=sesion.imagen_captcha, media_type="image/png")


@router.post("/sesiones/{sesion_id}/captcha", status_code=status.HTTP_204_NO_CONTENT)
async def responder_captcha(
    sesion_id: int,
    solicitud: SolicitudRespuestaCaptcha,
    caso_uso: ResponderCaptcha = Depends(construir_responder_captcha),
    _actor: CargaSesion = Depends(_OPERA_PLATAFORMAS),
) -> None:
    try:
        await caso_uso.ejecutar(sesion_id, solicitud.respuesta)
    except ErrorSesionNoEncontrada as error:
        raise ErrorAplicacion(
            "SESION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorSesionPlataforma as error:
        raise ErrorAplicacion(
            "SESION_PLATAFORMA_INVALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
