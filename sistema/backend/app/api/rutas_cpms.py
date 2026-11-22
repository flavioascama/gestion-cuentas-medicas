"""Seccion 11, 8.2: `GET /cpms/sugerencias`, `POST
/cuentas/{id}/procedimientos` y su `DELETE` para auditor; `GET`/`POST
/catalogo-cpms/versiones` para administrador (Fase 18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.dependencias_cpms import (
    construir_cargar_catalogo_cpms,
    construir_confirmar_codigo_cpms,
    construir_listar_versiones_cpms,
    construir_quitar_procedimiento,
    construir_sugerir_codigo_cpms,
)
from app.api.esquemas_cpms import (
    ParametrosSugerenciaCpms,
    ProcedimientoCatalogoCpmsRespuesta,
    ProcedimientoPorCodificarRespuesta,
    RespuestaCatalogoCpmsCargado,
    RespuestaProcedimientoConfirmado,
    RespuestaSugerenciaCpms,
    SolicitudCargarCatalogoCpms,
    SolicitudConfirmarProcedimiento,
    UltimoPrecioRespuesta,
    VersionCpmsRespuesta,
)
from app.api.serializacion import campos
from app.compartido.archivo_catalogo import ErrorArchivoCatalogoInvalido, decodificar_xlsx
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.cpms.casos_uso import (
    ConfirmacionCodigoCpms,
    ConfirmarCodigoCpms,
    ErrorCuentaNoCodificable,
    ErrorProcedimientoInexistente,
    ListarVersionesCpms,
    QuitarProcedimiento,
    SugerirCodigoCpms,
)
from app.dominio.cpms.normalizacion import normalizar
from app.dominio.cpms.por_codificar import (
    ErrorProcedimientoPorCodificarInexistente,
    ListarProcedimientosPorCodificar,
)
from app.dominio.cpms.puertos import ErrorCodigoCpmsInexistente, ErrorProcedimientoInvalido
from app.dominio.cpms.valores import FiltrosSugerencia
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.cpms.cargar_catalogo_cpms import CargarCatalogoCpms
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_cpms_sql import (
    ErrorRepositorioCpms,
    RepositorioCpmsSql,
)
from app.infraestructura.persistencia.repositorio_por_codificar_sql import (
    RepositorioProcedimientosPorCodificarSql,
)

router = APIRouter(tags=["cpms"])
_SOLO_AUDITOR = requiere_rol(NombreRol.AUDITOR)
_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)
_LECTURA_POR_CODIFICAR = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)


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
        procedimiento_por_codificar_id=solicitud.procedimiento_por_codificar_id,
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
    except ErrorProcedimientoInvalido as error:
        raise ErrorAplicacion(
            "PROCEDIMIENTO_INVALIDO", str(error), estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY
        ) from error
    except ErrorRepositorioCpms as error:
        raise ErrorAplicacion(
            "CATALOGO_CPMS_VACIO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorProcedimientoPorCodificarInexistente as error:
        raise ErrorAplicacion(
            "PROCEDIMIENTO_POR_CODIFICAR_NO_ENCONTRADO",
            str(error),
            estado_http=status.HTTP_404_NOT_FOUND,
        ) from error
    return RespuestaProcedimientoConfirmado(procedimiento_id=procedimiento_id)


@router.get(
    "/cuentas/{cuenta_id}/procedimientos-por-codificar",
    response_model=list[ProcedimientoPorCodificarRespuesta],
)
async def listar_procedimientos_por_codificar(
    cuenta_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA_POR_CODIFICAR),
) -> list[ProcedimientoPorCodificarRespuesta]:
    """Lo que trajo la atencion importada y aun no tiene codigo CPMS."""
    pendientes = await ListarProcedimientosPorCodificar(
        RepositorioProcedimientosPorCodificarSql(sesion)
    ).ejecutar(cuenta_id)
    return [ProcedimientoPorCodificarRespuesta(**campos(p)) for p in pendientes]


@router.delete(
    "/cuentas/{cuenta_id}/procedimientos/{procedimiento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def quitar_procedimiento(
    cuenta_id: int,
    procedimiento_id: int,
    caso_uso: QuitarProcedimiento = Depends(construir_quitar_procedimiento),
    actor: CargaSesion = Depends(_SOLO_AUDITOR),
) -> None:
    try:
        await caso_uso.ejecutar(cuenta_id, procedimiento_id, actor.nombre_usuario)
    except ErrorProcedimientoInexistente as error:
        raise ErrorAplicacion(
            "PROCEDIMIENTO_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorCuentaNoCodificable as error:
        raise ErrorAplicacion(
            "CUENTA_NO_CODIFICABLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error


@router.get(
    "/cuentas/{cuenta_id}/procedimientos/ultimo-precio", response_model=UltimoPrecioRespuesta
)
async def ultimo_precio_procedimiento(
    cuenta_id: int,
    codigo: str,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_SOLO_AUDITOR),
) -> UltimoPrecioRespuesta:
    """El precio que se propone al confirmar un procedimiento."""
    monto = await RepositorioCpmsSql(sesion).ultimo_monto_unitario(codigo, cuenta_id)
    return UltimoPrecioRespuesta(monto_unitario=monto)


@router.get("/catalogo-cpms/versiones", response_model=list[VersionCpmsRespuesta])
async def listar_versiones_cpms(
    caso_uso: ListarVersionesCpms = Depends(construir_listar_versiones_cpms),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[VersionCpmsRespuesta]:
    versiones = await caso_uso.ejecutar()
    return [VersionCpmsRespuesta.desde_valor(v) for v in versiones]


_MAXIMO_BUSQUEDA_CATALOGO = 20


@router.get(
    "/catalogo-cpms/procedimientos",
    response_model=list[ProcedimientoCatalogoCpmsRespuesta],
)
async def buscar_procedimientos_catalogo_cpms(
    buscar: str = Query(default="", max_length=100),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> list[ProcedimientoCatalogoCpmsRespuesta]:
    """Para que el administrador compruebe que un procedimiento esta en la
    version vigente: por codigo o nombre, sin distinguir mayusculas ni tildes."""
    texto = normalizar(buscar)
    if not texto:
        return []
    repositorio = RepositorioCpmsSql(sesion)
    try:
        version_id, _ = await repositorio.version_vigente()
    except ErrorRepositorioCpms:
        return []
    encontrados = sorted(
        (
            p
            for p in await repositorio.listar_procedimientos(version_id)
            if texto in normalizar(p.codigo) or texto in normalizar(p.denominacion)
        ),
        key=lambda p: p.codigo,
    )
    return [
        ProcedimientoCatalogoCpmsRespuesta(codigo=p.codigo, nombre=p.denominacion)
        for p in encontrados[:_MAXIMO_BUSQUEDA_CATALOGO]
    ]


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
        contenido = decodificar_xlsx(solicitud.nombre_archivo, solicitud.contenido_base64)
        resultado = await caso_uso.ejecutar(solicitud.etiqueta, solicitud.nombre_archivo, contenido)
    except ErrorArchivoCatalogoInvalido as error:
        raise ErrorAplicacion(
            "ARCHIVO_CATALOGO_INVALIDO",
            str(error),
            estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from error
    return RespuestaCatalogoCpmsCargado(
        version_id=resultado.version_id, etiqueta=resultado.etiqueta, conteo=resultado.conteo
    )
