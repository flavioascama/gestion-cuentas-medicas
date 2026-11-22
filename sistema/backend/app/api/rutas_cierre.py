"""CU-13 (RF-08, RF-16, RF-21): el cierre y la solicitud de anulacion
son del analista de cuentas medicas; aprobar o rechazar la anulacion es
exclusivo del jefe de cuentas medicas (Fase 28)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.dependencias_cierre import (
    construir_cerrar_cuenta,
    construir_consultar_cierre_cuenta,
    construir_listar_solicitudes_anulacion_pendientes,
    construir_resolver_solicitud_anulacion,
    construir_solicitar_anulacion,
)
from app.api.esquemas_cierre import (
    EstadoCierreRespuesta,
    RespuestaCierre,
    RespuestaResolucionAnulacion,
    RespuestaSolicitudAnulacion,
    SolicitudAnulacionRespuesta,
    SolicitudNuevaAnulacion,
    SolicitudResolucionAnulacion,
)
from app.api.mensajes_transicion import mensaje_operacion_no_disponible
from app.api.nombres_actores import con_nombres_en_filas
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.cierre.casos_uso import (
    CerrarCuenta,
    ConsultarCierreCuenta,
    ListarSolicitudesAnulacionPendientes,
    ResolverSolicitudAnulacion,
    SolicitarAnulacion,
)
from app.dominio.cierre.errores import (
    ErrorAnulacionPropia,
    ErrorDiferenciaPendiente,
    ErrorMotivoRechazoRequerido,
    ErrorObservacionPendiente,
    ErrorSinLiquidacion,
    ErrorSolicitudAnulacionInexistente,
    ErrorSolicitudAnulacionYaPendiente,
    ErrorSolicitudAnulacionYaResuelta,
)
from app.dominio.orquestacion.errores import ErrorAnulacionSinAprobacion, ErrorTransicionNoDefinida
from app.infraestructura.persistencia.base import obtener_sesion

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["cierre"])
router_anulaciones = APIRouter(prefix="/anulaciones", tags=["cierre"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_SOLO_JEFE = requiere_rol(NombreRol.JEFE)


@router.get("/cierre", response_model=EstadoCierreRespuesta)
async def consultar_cierre_cuenta(
    cuenta_id: int,
    caso_uso: ConsultarCierreCuenta = Depends(construir_consultar_cierre_cuenta),
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> EstadoCierreRespuesta:
    return EstadoCierreRespuesta.desde_valor(await caso_uso.ejecutar(cuenta_id))


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
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
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
        # SolicitarAnulacion ya redacta el motivo para el usuario.
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
    sesion: AsyncSession = Depends(obtener_sesion),
) -> list[SolicitudAnulacionRespuesta]:
    solicitudes = [SolicitudAnulacionRespuesta.desde_valor(s) for s in await caso_uso.ejecutar()]
    await con_nombres_en_filas(sesion, solicitudes, {"solicitado_por": "solicitado_por_nombre"})
    return solicitudes


@router_anulaciones.post("/{solicitud_id}/resolucion", response_model=RespuestaResolucionAnulacion)
async def resolver_solicitud_anulacion(
    solicitud_id: int,
    solicitud: SolicitudResolucionAnulacion,
    caso_uso: ResolverSolicitudAnulacion = Depends(construir_resolver_solicitud_anulacion),
    actor: CargaSesion = Depends(_SOLO_JEFE),
) -> RespuestaResolucionAnulacion:
    try:
        estado_nuevo = await caso_uso.ejecutar(
            solicitud_id, solicitud.aprobada, actor.nombre_usuario, solicitud.motivo
        )
    except ErrorSolicitudAnulacionInexistente as error:
        raise ErrorAplicacion(
            "SOLICITUD_ANULACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorMotivoRechazoRequerido as error:
        raise ErrorAplicacion(
            "MOTIVO_RECHAZO_REQUERIDO",
            str(error),
            estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from error
    except ErrorAnulacionPropia as error:
        raise ErrorAplicacion(
            "ANULACION_PROPIA", str(error), estado_http=status.HTTP_403_FORBIDDEN
        ) from error
    except ErrorSolicitudAnulacionYaResuelta as error:
        raise ErrorAplicacion(
            "SOLICITUD_ANULACION_YA_RESUELTA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorAnulacionSinAprobacion as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    return RespuestaResolucionAnulacion(estado_cuenta=estado_nuevo)
