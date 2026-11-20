"""Modo de contingencia (RF-23, AD-13, C-18; Tabla 46: "registrar un
resultado en modo de contingencia", solo el analista). La revision
posterior de cada registro es del jefe de cuentas medicas (C-18)."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_contingencia import (
    construir_disponibilidad_contingencia,
    construir_listar_registros_contingencia,
    construir_registrar_cobertura_contingencia,
    construir_registrar_validacion_contingencia,
    construir_revisar_registro_contingencia,
    construir_ultima_consulta_cobertura,
)
from app.api.esquemas_contingencia import (
    DisponibilidadContingenciaRespuesta,
    RegistroContingenciaRespuesta,
    RespuestaCoberturaContingencia,
    RespuestaValidacionContingencia,
    SolicitudCoberturaContingencia,
    SolicitudRevisionContingencia,
    SolicitudValidacionContingencia,
    UltimaConsultaCoberturaRespuesta,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.acreditacion.puertos import ErrorCuentaNoEncontrada
from app.dominio.acreditacion.valores import ResultadoAcreditacion
from app.dominio.contingencia.casos_uso import (
    ConsultarDisponibilidadContingencia,
    ConsultarUltimaConsultaCobertura,
    ListarRegistrosContingencia,
    RegistrarCoberturaContingencia,
    RevisarRegistroContingencia,
    normalizar_copago,
)
from app.dominio.contingencia.errores import (
    ErrorArchivoS01Invalido,
    ErrorContingenciaNoHabilitada,
    ErrorCopagoIncompleto,
    ErrorRegistroContingenciaInexistente,
    ErrorRegistroContingenciaYaRevisado,
    ErrorSustentoInsuficiente,
)
from app.dominio.integracion.puertos_validacion import ArchivoLote
from app.infraestructura.tedef.registrar_validacion_contingencia import (
    RegistrarValidacionContingencia,
)

router_cuentas = APIRouter(prefix="/cuentas/{cuenta_id}/cobertura", tags=["contingencia"])
router_lotes = APIRouter(prefix="/lotes/{lote_id}/validacion", tags=["contingencia"])
router = APIRouter(prefix="/contingencias", tags=["contingencia"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_SOLO_JEFE = requiere_rol(NombreRol.JEFE)


def _error_contingencia(error: Exception) -> ErrorAplicacion:
    if isinstance(error, ErrorContingenciaNoHabilitada):
        return ErrorAplicacion(
            "CONTINGENCIA_NO_HABILITADA", str(error), estado_http=status.HTTP_409_CONFLICT
        )
    codigo = (
        "SUSTENTO_INSUFICIENTE"
        if isinstance(error, ErrorSustentoInsuficiente)
        else ("ARCHIVO_S01_INVALIDO")
    )
    return ErrorAplicacion(codigo, str(error), estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY)


@router_cuentas.get("/ultima-consulta", response_model=UltimaConsultaCoberturaRespuesta | None)
async def ultima_consulta_cobertura(
    cuenta_id: int,
    caso_uso: ConsultarUltimaConsultaCobertura = Depends(construir_ultima_consulta_cobertura),
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> UltimaConsultaCoberturaRespuesta | None:
    """Como termino la ultima consulta de ACREDITA SALUD de la cuenta (null
    si nunca se consulto)."""
    ultima = await caso_uso.ejecutar(cuenta_id)
    return UltimaConsultaCoberturaRespuesta.desde_valor(ultima) if ultima else None


@router_cuentas.get("/contingencia", response_model=DisponibilidadContingenciaRespuesta)
async def disponibilidad_cobertura_contingencia(
    cuenta_id: int,
    caso_uso: ConsultarDisponibilidadContingencia = Depends(construir_disponibilidad_contingencia),
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> DisponibilidadContingenciaRespuesta:
    return DisponibilidadContingenciaRespuesta(habilitada=await caso_uso.cobertura(cuenta_id))


@router_cuentas.post(
    "/contingencia",
    response_model=RespuestaCoberturaContingencia,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_cobertura_contingencia(
    cuenta_id: int,
    solicitud: SolicitudCoberturaContingencia,
    caso_uso: RegistrarCoberturaContingencia = Depends(construir_registrar_cobertura_contingencia),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaCoberturaContingencia:
    try:
        acreditacion_id = await caso_uso.ejecutar(
            cuenta_id, resultado_contingencia(solicitud), solicitud.sustento, actor.nombre_usuario
        )
    except ErrorCuentaNoEncontrada as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except (ErrorContingenciaNoHabilitada, ErrorSustentoInsuficiente) as error:
        raise _error_contingencia(error) from error
    except ErrorCopagoIncompleto as error:
        raise ErrorAplicacion(
            "COPAGO_INCOMPLETO", str(error), estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY
        ) from error
    return RespuestaCoberturaContingencia(acreditacion_id=acreditacion_id)


def resultado_contingencia(solicitud: SolicitudCoberturaContingencia) -> ResultadoAcreditacion:
    """La acreditacion registrada a mano, con el plan y el copago en el
    mismo formato que deja el robot."""
    tipo, monto, porcentaje = normalizar_copago(
        solicitud.tipo_copago, solicitud.monto_copago_fijo, solicitud.porcentaje_coaseguro
    )
    return ResultadoAcreditacion(
        condicion_cobertura=solicitud.condicion_cobertura,
        codigo_autorizacion=solicitud.codigo_autorizacion,
        tipo_documento_autorizacion=solicitud.tipo_documento_autorizacion,
        codigo_asegurado=solicitud.codigo_asegurado,
        tipo_afiliacion=solicitud.tipo_afiliacion,
        plan=(solicitud.plan or "").strip() or None,
        vigente_desde=None,
        vigente_hasta=solicitud.vigente_hasta,
        tipo_copago=tipo,
        monto_copago_fijo=monto,
        porcentaje_coaseguro=porcentaje,
    )


@router_lotes.get("/contingencia", response_model=DisponibilidadContingenciaRespuesta)
async def disponibilidad_validacion_contingencia(
    lote_id: int,
    caso_uso: ConsultarDisponibilidadContingencia = Depends(construir_disponibilidad_contingencia),
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> DisponibilidadContingenciaRespuesta:
    return DisponibilidadContingenciaRespuesta(habilitada=await caso_uso.validacion(lote_id))


def _archivo_desde_solicitud(solicitud: SolicitudValidacionContingencia) -> ArchivoLote | None:
    if not solicitud.nombre_s01 or not solicitud.contenido_s01_base64:
        return None
    try:
        contenido = base64.b64decode(solicitud.contenido_s01_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ErrorArchivoS01Invalido("El contenido del .S01 no es base64 valido.") from error
    return ArchivoLote(nombre=solicitud.nombre_s01, contenido=contenido)


@router_lotes.post("/contingencia", response_model=RespuestaValidacionContingencia)
async def registrar_validacion_contingencia(
    lote_id: int,
    solicitud: SolicitudValidacionContingencia,
    caso_uso: RegistrarValidacionContingencia = Depends(
        construir_registrar_validacion_contingencia
    ),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaValidacionContingencia:
    try:
        estado = await caso_uso.ejecutar(
            lote_id,
            solicitud.resultado,
            solicitud.sustento,
            _archivo_desde_solicitud(solicitud),
            actor.nombre_usuario,
        )
    except (
        ErrorContingenciaNoHabilitada,
        ErrorSustentoInsuficiente,
        ErrorArchivoS01Invalido,
    ) as error:
        raise _error_contingencia(error) from error
    return RespuestaValidacionContingencia(estado_lote=estado)


@router.get("", response_model=list[RegistroContingenciaRespuesta])
async def listar_registros_contingencia(
    caso_uso: ListarRegistrosContingencia = Depends(construir_listar_registros_contingencia),
    _actor: CargaSesion = Depends(_SOLO_JEFE),
) -> list[RegistroContingenciaRespuesta]:
    return [RegistroContingenciaRespuesta.desde_valor(r) for r in await caso_uso.ejecutar()]


@router.post("/{evento_id}/revision", status_code=status.HTTP_204_NO_CONTENT)
async def revisar_registro_contingencia(
    evento_id: str,
    solicitud: SolicitudRevisionContingencia,
    caso_uso: RevisarRegistroContingencia = Depends(construir_revisar_registro_contingencia),
    actor: CargaSesion = Depends(_SOLO_JEFE),
) -> None:
    try:
        await caso_uso.ejecutar(
            evento_id, solicitud.conforme, solicitud.comentario, actor.nombre_usuario
        )
    except ErrorRegistroContingenciaInexistente as error:
        raise ErrorAplicacion(
            "REGISTRO_CONTINGENCIA_INEXISTENTE", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorRegistroContingenciaYaRevisado as error:
        raise ErrorAplicacion(
            "REGISTRO_CONTINGENCIA_YA_REVISADO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
