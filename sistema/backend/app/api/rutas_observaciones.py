"""Seccion 5.2.4.2: /observaciones (CU-08 a CU-10, Fase 26). Registrar y
clasificar es del analista (CU-08); asignar o reasignar el responsable es
del jefe (CU-09); responder es de quien quedo como responsable segun la
naturaleza -- analista (ADMINISTRATIVA/FINANCIERA) o auditor (TECNICA),
Tabla 60 -- por eso la ruta de respuesta admite ambos roles y no uno solo."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.dependencias_comunicaciones import (
    construir_encolar_respuesta_iafas,
    construir_solicitar_nueva_entrega,
)
from app.api.dependencias_observaciones import (
    construir_asignar_responsable_observacion,
    construir_listar_catalogo_motivos,
    construir_listar_observaciones_por_cuenta,
    construir_listar_responsables_posibles,
    construir_registrar_observacion,
    construir_responder_observacion,
)
from app.api.esquemas_observaciones import (
    MotivoObservacionRespuesta,
    ObservacionRespuesta,
    ResponsablePosibleRespuesta,
    RespuestaNuevaEntrega,
    RespuestaObservacionRegistrada,
    SolicitudAdjuntoRespuesta,
    SolicitudAsignacionObservacion,
    SolicitudRegistroObservacion,
    SolicitudRespuestaObservacion,
)
from app.api.mensajes_transicion import mensaje_operacion_no_disponible
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.casos_uso import EncolarRespuestaIafas
from app.dominio.comunicaciones.entrega_respuesta import (
    ErrorEntregaDeOtro,
    ErrorEntregaNoDisponible,
    Solicitante,
    SolicitarNuevaEntregaRespuesta,
)
from app.dominio.observaciones.adjunto_respuesta import ErrorAdjuntoNoValido, leer_adjunto
from app.dominio.observaciones.casos_uso import (
    AsignarResponsableObservacion,
    ListarCatalogoMotivos,
    ListarObservacionesPorCuenta,
    ListarResponsablesPosibles,
    RegistrarObservacion,
    ResponderObservacion,
)
from app.dominio.observaciones.errores import (
    ErrorMontoObservadoExcedeFacturado,
    ErrorMontoObservadoNoValido,
    ErrorMotivoInexistente,
    ErrorObservacionDeOtroResponsable,
    ErrorObservacionInexistente,
    ErrorObservacionYaRespondida,
    ErrorResponsableNoValido,
    ErrorRespuestaConComprobanteDesfasado,
)
from app.dominio.observaciones.valores import (
    ROL_RESPONSABLE_POR_NATURALEZA,
    DatosRegistroObservacion,
    Respondedor,
)
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.infraestructura.persistencia.adjunto_respuesta_sql import (
    guardar_adjunto,
    nombres_de_adjuntos,
    obtener_adjunto,
)
from app.infraestructura.persistencia.base import obtener_sesion

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
                monto_observado=solicitud.monto_observado,
            )
        )
    except ErrorMotivoInexistente as error:
        raise ErrorAplicacion(
            "MOTIVO_INEXISTENTE", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except ErrorMontoObservadoExcedeFacturado as error:
        raise ErrorAplicacion(
            "MONTO_EXCEDIDO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorMontoObservadoNoValido as error:
        raise ErrorAplicacion(
            "MONTO_NO_VALIDO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    return RespuestaObservacionRegistrada.desde_valor(resultado)


@router.get("", response_model=list[ObservacionRespuesta])
async def listar_observaciones_de_cuenta(
    cuenta_id: int,
    caso_uso: ListarObservacionesPorCuenta = Depends(construir_listar_observaciones_por_cuenta),
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ObservacionRespuesta]:
    observaciones = await caso_uso.ejecutar(cuenta_id)
    adjuntos = await nombres_de_adjuntos(sesion, [o.id for o in observaciones])
    return [
        ObservacionRespuesta.desde_valor(o).model_copy(
            update={"adjunto_nombre": adjuntos.get(o.id)}
        )
        for o in observaciones
    ]


@router_item.get("/motivos", response_model=list[MotivoObservacionRespuesta])
async def listar_motivos(
    caso_uso: ListarCatalogoMotivos = Depends(construir_listar_catalogo_motivos),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[MotivoObservacionRespuesta]:
    motivos = await caso_uso.ejecutar()
    return [MotivoObservacionRespuesta.desde_valor(m) for m in motivos]


@router_item.get("/responsables", response_model=list[ResponsablePosibleRespuesta])
async def listar_responsables_posibles(
    caso_uso: ListarResponsablesPosibles = Depends(construir_listar_responsables_posibles),
    _actor: CargaSesion = Depends(_SOLO_JEFE),
) -> list[ResponsablePosibleRespuesta]:
    """CU-09: las personas entre las que el jefe elige al responsable."""
    roles = frozenset(ROL_RESPONSABLE_POR_NATURALEZA.values())
    usuarios = await caso_uso.ejecutar()
    return [ResponsablePosibleRespuesta.desde_usuario(u, roles) for u in usuarios]


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
    except ErrorResponsableNoValido as error:
        raise ErrorAplicacion(
            "RESPONSABLE_NO_VALIDO", str(error), estado_http=status.HTTP_400_BAD_REQUEST
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
    se le remite por su portal, con su documento adjunto si lo hay: queda
    encolada para el robot."""
    try:
        await caso_uso.ejecutar(
            observacion_id,
            solicitud.respuesta_texto,
            solicitud.respuesta_sustento,
            actor.nombre_usuario,
            respondedor=Respondedor(actor.usuario_id, actor.nombre_usuario, actor.roles),
        )
    except ErrorObservacionInexistente as error:
        raise ErrorAplicacion(
            "OBSERVACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorObservacionDeOtroResponsable as error:
        raise ErrorAplicacion(
            "OBSERVACION_DE_OTRO_RESPONSABLE", str(error), estado_http=status.HTTP_403_FORBIDDEN
        ) from error
    except ErrorObservacionYaRespondida as error:
        raise ErrorAplicacion(
            "OBSERVACION_YA_RESPONDIDA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorRespuestaConComprobanteDesfasado as error:
        raise ErrorAplicacion(
            "COMPROBANTE_DESFASADO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorTransicionNoDefinida as error:
        raise ErrorAplicacion(
            "TRANSICION_NO_VALIDA",
            mensaje_operacion_no_disponible(error),
            estado_http=status.HTTP_409_CONFLICT,
        ) from error
    await remision.ejecutar(
        observacion_id,
        solicitud.respuesta_texto,
        solicitud.respuesta_sustento,
        actor.nombre_usuario,
    )


@router_item.put("/{observacion_id}/adjunto", status_code=status.HTTP_204_NO_CONTENT)
async def adjuntar_documento_respuesta(
    observacion_id: int,
    solicitud: SolicitudAdjuntoRespuesta,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_RESPONDE),
) -> None:
    """El PDF que acompana la respuesta: se sube antes de responder."""
    try:
        adjunto = leer_adjunto(solicitud.nombre, solicitud.contenido_base64)
        await guardar_adjunto(sesion, observacion_id, adjunto, actor.nombre_usuario)
    except ErrorAdjuntoNoValido as error:
        raise ErrorAplicacion(
            "ADJUNTO_NO_VALIDO", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error


@router_item.get("/{observacion_id}/adjunto")
async def descargar_adjunto_respuesta(
    observacion_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> Response:
    adjunto = await obtener_adjunto(sesion, observacion_id)
    if adjunto is None:
        raise ErrorAplicacion(
            "ADJUNTO_NO_ENCONTRADO",
            "La respuesta no tiene un documento adjunto.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    # Siempre como descarga, igual que los adjuntos de los correos.
    return Response(
        content=adjunto.contenido,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(adjunto.nombre)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router_item.post("/{observacion_id}/entrega", response_model=RespuestaNuevaEntrega)
async def pedir_nueva_entrega(
    observacion_id: int,
    caso_uso: SolicitarNuevaEntregaRespuesta = Depends(construir_solicitar_nueva_entrega),
    actor: CargaSesion = Depends(_RESPONDE),
) -> RespuestaNuevaEntrega:
    """Vuelve a encolar la entrega de la respuesta a la aseguradora cuando
    la anterior agoto sus intentos (2026-11-19)."""
    try:
        trabajo_id = await caso_uso.ejecutar(
            observacion_id, Solicitante(actor.nombre_usuario, actor.roles)
        )
    except ErrorObservacionInexistente as error:
        raise ErrorAplicacion(
            "OBSERVACION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorEntregaDeOtro as error:
        raise ErrorAplicacion(
            "ENTREGA_DE_OTRO_RESPONSABLE", str(error), estado_http=status.HTTP_403_FORBIDDEN
        ) from error
    except ErrorEntregaNoDisponible as error:
        raise ErrorAplicacion(
            "ENTREGA_NO_DISPONIBLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaNuevaEntrega(trabajo_id=trabajo_id)
