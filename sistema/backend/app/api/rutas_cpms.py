"""Seccion 11, 8.2: `GET /cpms/sugerencias` y `POST
/cuentas/{id}/procedimientos` para auditor; `GET`/`POST
/catalogo-cpms/versiones` para administrador (Fase 18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.dependencias_cpms import (
    construir_cargar_catalogo_cpms,
    construir_confirmar_codigo_cpms,
    construir_listar_versiones_cpms,
    construir_sugerir_codigo_cpms,
)
from app.api.esquemas_cpms import (
    ParametrosSugerenciaCpms,
    RespuestaCatalogoCpmsCargado,
    RespuestaProcedimientoConfirmado,
    RespuestaSugerenciaCpms,
    SolicitudCargarCatalogoCpms,
    SolicitudConfirmarProcedimiento,
    VersionCpmsRespuesta,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.cpms.casos_uso import (
    ConfirmacionCodigoCpms,
    ConfirmarCodigoCpms,
    ErrorCuentaNoCodificable,
    ListarVersionesCpms,
    SugerirCodigoCpms,
)
from app.dominio.cpms.puertos import ErrorCodigoCpmsInexistente
from app.dominio.cpms.valores import FiltrosSugerencia
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.cpms.cargar_catalogo_cpms import CargarCatalogoCpms, ErrorSinArchivosCpms
from app.infraestructura.persistencia.repositorio_cpms_sql import ErrorRepositorioCpms

router = APIRouter(tags=["cpms"])
_SOLO_AUDITOR = requiere_rol(NombreRol.AUDITOR)
_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)


@router.get("/cpms/sugerencias", response_model=RespuestaSugerenciaCpms)
async def sugerir_codigo_cpms(
    parametros: ParametrosSugerenciaCpms = Depends(),
    # `actor` antes que `caso_uso` (a diferencia del resto de las rutas):
    # construir_sugerir_codigo_cpms reconstruye el indice TF-IDF si hace
    # falta (Seccion 8.2, punto 7), costoso y solo tiene sentido para un
    # actor ya autorizado -- FastAPI resuelve las dependencias en el orden
    # de los parametros, asi que este orden evita ese trabajo (y la
    # excepcion sin capturar si aun no hay catalogo CPMS) en un 401/403.
    actor: CargaSesion = Depends(_SOLO_AUDITOR),
    caso_uso: SugerirCodigoCpms = Depends(construir_sugerir_codigo_cpms),
    reloj: Reloj = Depends(obtener_reloj),
) -> RespuestaSugerenciaCpms:
    inicio_sugerencia = reloj.ahora()
    filtros = FiltrosSugerencia(
        codigo_grupo=parametros.codigo_grupo,
        codigo_seccion=parametros.codigo_seccion,
        codigo_subseccion=parametros.codigo_subseccion,
    )
    resultado = await caso_uso.ejecutar(
        parametros.descripcion, filtros, actor.nombre_usuario, parametros.cuenta_medica_id
    )
    return RespuestaSugerenciaCpms.desde_valor(resultado, inicio_sugerencia)


@router.post(
    "/cuentas/{cuenta_id}/procedimientos",
    response_model=RespuestaProcedimientoConfirmado,
    status_code=status.HTTP_201_CREATED,
)
async def confirmar_procedimiento(
    cuenta_id: int,
    solicitud: SolicitudConfirmarProcedimiento,
    caso_uso: ConfirmarCodigoCpms = Depends(construir_confirmar_codigo_cpms),
    actor: CargaSesion = Depends(_SOLO_AUDITOR),
) -> RespuestaProcedimientoConfirmado:
    confirmacion = ConfirmacionCodigoCpms(
        cuenta_medica_id=cuenta_id,
        descripcion_registrada=solicitud.descripcion_registrada,
        codigo_elegido=solicitud.codigo_elegido,
        posicion_aceptada=solicitud.posicion_aceptada,
        usuario_confirmo_id=actor.usuario_id,
        cantidad=solicitud.cantidad,
        monto_unitario=solicitud.monto_unitario,
        fecha=solicitud.fecha,
    )
    try:
        procedimiento_id = await caso_uso.ejecutar(
            confirmacion, actor.nombre_usuario, solicitud.inicio_sugerencia
        )
    except ErrorCodigoCpmsInexistente as error:
        raise ErrorAplicacion(
            "CODIGO_CPMS_INEXISTENTE", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except ErrorCuentaNoCodificable as error:
        raise ErrorAplicacion(
            "CUENTA_NO_CODIFICABLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorRepositorioCpms as error:
        raise ErrorAplicacion(
            "CATALOGO_CPMS_VACIO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaProcedimientoConfirmado(procedimiento_id=procedimiento_id)


@router.get("/catalogo-cpms/versiones", response_model=list[VersionCpmsRespuesta])
async def listar_versiones_cpms(
    caso_uso: ListarVersionesCpms = Depends(construir_listar_versiones_cpms),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[VersionCpmsRespuesta]:
    versiones = await caso_uso.ejecutar()
    return [VersionCpmsRespuesta.desde_valor(v) for v in versiones]


@router.post(
    "/catalogo-cpms/versiones",
    response_model=RespuestaCatalogoCpmsCargado,
    status_code=status.HTTP_201_CREATED,
)
async def cargar_catalogo_cpms(
    solicitud: SolicitudCargarCatalogoCpms,
    caso_uso: CargarCatalogoCpms = Depends(construir_cargar_catalogo_cpms),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> RespuestaCatalogoCpmsCargado:
    try:
        resultado = await caso_uso.ejecutar(solicitud.etiqueta)
    except ErrorSinArchivosCpms as error:
        raise ErrorAplicacion(
            "SIN_ARCHIVOS_CPMS", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaCatalogoCpmsCargado(
        version_id=resultado.version_id, etiqueta=resultado.etiqueta, conteo=resultado.conteo
    )
