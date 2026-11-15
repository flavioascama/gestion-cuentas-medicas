"""Seccion 5.2.4.2: /observaciones (CU-08 a CU-10, Fase 26). Registrar y
clasificar es del analista (CU-08); asignar o reasignar el responsable es
del jefe (CU-09); responder es de quien quedo como responsable segun la
naturaleza -- analista (ADMINISTRATIVA/FINANCIERA) o auditor (TECNICA),
Tabla 60 -- por eso la ruta de respuesta admite ambos roles y no uno solo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_comunicaciones import construir_encolar_respuesta_iafas
from app.api.dependencias_observaciones import (
    construir_asignar_responsable_observacion,
    construir_listar_catalogo_motivos,
    construir_listar_observaciones_por_cuenta,
    construir_registrar_observacion,
    construir_responder_observacion,
)
from app.api.esquemas_observaciones import (
    MotivoObservacionRespuesta,
    ObservacionRespuesta,
    RespuestaObservacionRegistrada,
    SolicitudAsignacionObservacion,
    SolicitudRegistroObservacion,
    SolicitudRespuestaObservacion,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.casos_uso import EncolarRespuestaIafas
from app.dominio.observaciones.casos_uso import (
    AsignarResponsableObservacion,
    ListarCatalogoMotivos,
    ListarObservacionesPorCuenta,
    RegistrarObservacion,
    ResponderObservacion,
)
from app.dominio.observaciones.errores import (
    ErrorMotivoInexistente,
    ErrorObservacionInexistente,
    ErrorObservacionYaRespondida,
)
from app.dominio.observaciones.valores import DatosRegistroObservacion
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida

router = APIRouter(prefix="/cuentas/{cuenta_id}/observaciones", tags=["observaciones"])
router_item = APIRouter(prefix="/observaciones", tags=["observaciones"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_SOLO_JEFE = requiere_rol(NombreRol.JEFE)
_RESPONDE = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)


@router.post("", response_model=RespuestaObservacionRegistrada, status_code=status.HTTP_201_CREATED)
async def registrar_observacion(
    cuenta_id: int,
    solicitud: SolicitudRegistroObservacion,
    caso_uso: RegistrarObservacion = Depends(construir_registrar_observacion),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaObservacionRegistrada:
    try:
        resultado = await caso_uso.ejecutar(
            DatosRegistroObservacion(
                cuenta_medica_id=cuenta_id,
                motivo_codigo=solicitud.motivo_codigo,
                es_parcial=solicitud.es_parcial,
                detalle_campo_objetado=solicitud.detalle_campo_objetado,
                actor=actor.nombre_usuario,
                usuario_origen=actor.nombre_usuario,
            )
        )
    except ErrorMotivoInexistente as error:
        raise ErrorAplicacion(
            "MOTIVO_INEXISTENTE", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaObservacionRegistrada.desde_valor(resultado)


@router.get("", response_model=list[ObservacionRespuesta])
async def listar_observaciones_de_cuenta(
    cuenta_id: int,
    caso_uso: ListarObservacionesPorCuenta = Depends(construir_listar_observaciones_por_cuenta),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ObservacionRespuesta]:
    observaciones = await caso_uso.ejecutar(cuenta_id)
    return [ObservacionRespuesta.desde_valor(o) for o in observaciones]


@router_item.get("/motivos", response_model=list[MotivoObservacionRespuesta])
async def listar_motivos(
    caso_uso: ListarCatalogoMotivos = Depends(construir_listar_catalogo_motivos),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[MotivoObservacionRespuesta]:
    motivos = await caso_uso.ejecutar()
    return [MotivoObservacionRespuesta.desde_valor(m) for m in motivos]


@router_item.patch("/{observacion_id}/asignacion", status_code=status.HTTP_204_NO_CONTENT)
async def asignar_responsable(
    observacion_id: int,
    solicitud: SolicitudAsignacionObservacion,
    caso_uso: AsignarResponsableObservacion = Depends(construir_asignar_responsable_observacion),
    actor: CargaSesion = Depends(_SOLO_JEFE),
) -> None:
    try:
        await caso_uso.ejecutar(
            observacion_id,
            actor.nombre_usuario,
            solicitud.responsable_usuario_id,
            solicitud.naturaleza_corregida,
        )
    except ErrorObservacionInexistente as error:
        raise ErrorAplicacion(
            "OBSERVACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error


@router_item.post("/{observacion_id}/respuesta", status_code=status.HTTP_204_NO_CONTENT)
async def responder_observacion(
    observacion_id: int,
    solicitud: SolicitudRespuestaObservacion,
    caso_uso: ResponderObservacion = Depends(construir_responder_observacion),
    remision: EncolarRespuestaIafas = Depends(construir_encolar_respuesta_iafas),
    actor: CargaSesion = Depends(_RESPONDE),
) -> None:
    """Si la observacion llego de la IAFAS (portal o correo), la respuesta
    se le remite por su portal: queda encolada para el robot."""
    try:
        await caso_uso.ejecutar(
            observacion_id,
            solicitud.respuesta_texto,
            solicitud.respuesta_sustento,
            actor.nombre_usuario,
            usuario_origen=actor.nombre_usuario,
        )
    except ErrorObservacionInexistente as error:
        raise ErrorAplicacion(
            "OBSERVACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorObservacionYaRespondida as error:
        raise ErrorAplicacion(
            "OBSERVACION_YA_RESPONDIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    await remision.ejecutar(
        observacion_id,
        solicitud.respuesta_texto,
        solicitud.respuesta_sustento,
        actor.nombre_usuario,
    )
