"""CU-13 (RF-08, RF-16, RF-21): el cierre y la solicitud de anulacion
son del analista de cuentas medicas; aprobar o rechazar la anulacion es
exclusivo del jefe de cuentas medicas (Fase 28)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_cierre import (
    construir_cerrar_cuenta,
    construir_listar_solicitudes_anulacion_pendientes,
    construir_resolver_solicitud_anulacion,
    construir_solicitar_anulacion,
)
from app.api.esquemas_cierre import (
    RespuestaCierre,
    RespuestaResolucionAnulacion,
    RespuestaSolicitudAnulacion,
    SolicitudAnulacionRespuesta,
    SolicitudNuevaAnulacion,
    SolicitudResolucionAnulacion,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.cierre.casos_uso import (
    CerrarCuenta,
    ListarSolicitudesAnulacionPendientes,
    ResolverSolicitudAnulacion,
    SolicitarAnulacion,
)
from app.dominio.cierre.errores import (
    ErrorDiferenciaPendiente,
    ErrorObservacionPendiente,
    ErrorSinLiquidacion,
    ErrorSolicitudAnulacionInexistente,
    ErrorSolicitudAnulacionYaPendiente,
    ErrorSolicitudAnulacionYaResuelta,
)
from app.dominio.orquestacion.errores import ErrorAnulacionSinAprobacion, ErrorTransicionNoDefinida

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["cierre"])
router_anulaciones = APIRouter(prefix="/anulaciones", tags=["cierre"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_SOLO_JEFE = requiere_rol(NombreRol.JEFE)


@router.post("/cierre", response_model=RespuestaCierre)
async def cerrar_cuenta(
    cuenta_id: int,
    caso_uso: CerrarCuenta = Depends(construir_cerrar_cuenta),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaCierre:
    try:
        estado_nuevo = await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except (ErrorSinLiquidacion, ErrorDiferenciaPendiente, ErrorObservacionPendiente) as error:
        raise ErrorAplicacion(
            "CIERRE_NO_PROCEDE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaCierre(estado_cuenta=estado_nuevo)


@router.post(
    "/anulacion/solicitud",
    response_model=RespuestaSolicitudAnulacion,
    status_code=status.HTTP_201_CREATED,
)
async def solicitar_anulacion(
    cuenta_id: int,
    solicitud: SolicitudNuevaAnulacion,
    caso_uso: SolicitarAnulacion = Depends(construir_solicitar_anulacion),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaSolicitudAnulacion:
    try:
        solicitud_id = await caso_uso.ejecutar(cuenta_id, solicitud.motivo, actor.nombre_usuario)
    except ErrorSolicitudAnulacionYaPendiente as error:
        raise ErrorAplicacion(
            "SOLICITUD_ANULACION_YA_PENDIENTE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaSolicitudAnulacion(solicitud_id=solicitud_id)


@router_anulaciones.get("/pendientes", response_model=list[SolicitudAnulacionRespuesta])
async def listar_solicitudes_anulacion_pendientes(
    caso_uso: ListarSolicitudesAnulacionPendientes = Depends(
        construir_listar_solicitudes_anulacion_pendientes
    ),
    _actor: CargaSesion = Depends(_SOLO_JEFE),
) -> list[SolicitudAnulacionRespuesta]:
    solicitudes = await caso_uso.ejecutar()
    return [SolicitudAnulacionRespuesta.desde_valor(s) for s in solicitudes]


@router_anulaciones.post("/{solicitud_id}/resolucion", response_model=RespuestaResolucionAnulacion)
async def resolver_solicitud_anulacion(
    solicitud_id: int,
    solicitud: SolicitudResolucionAnulacion,
    caso_uso: ResolverSolicitudAnulacion = Depends(construir_resolver_solicitud_anulacion),
    actor: CargaSesion = Depends(_SOLO_JEFE),
) -> RespuestaResolucionAnulacion:
    try:
        estado_nuevo = await caso_uso.ejecutar(
            solicitud_id, solicitud.aprobada, actor.nombre_usuario
        )
    except ErrorSolicitudAnulacionInexistente as error:
        raise ErrorAplicacion(
            "SOLICITUD_ANULACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorSolicitudAnulacionYaResuelta as error:
        raise ErrorAplicacion(
            "SOLICITUD_ANULACION_YA_RESUELTA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except (ErrorTransicionNoDefinida, ErrorAnulacionSinAprobacion) as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaResolucionAnulacion(estado_cuenta=estado_nuevo)
