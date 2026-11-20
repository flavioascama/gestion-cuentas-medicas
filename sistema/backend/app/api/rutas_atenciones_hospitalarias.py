"""Importar la atencion cerrada desde el sistema hospitalario (2026-11-19):
`GET /atenciones-hospitalarias`, `POST
/atenciones-hospitalarias/{atencion_id}/importar` (via consulta) y `POST
/cuentas/importar` (via archivo), para el analista. Ademas `GET
/cuentas/{id}/copago-cobrado` y `GET /cuentas/{id}/copago-asegurado`, de
lectura, y `POST /cuentas/{id}/copago-cobrado` (registro manual, analista)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.esquemas_atenciones import (
    CopagoAseguradoRespuesta,
    CopagoCobradoRespuesta,
    ResumenAtencionRespuesta,
    SolicitudCopagoCobrado,
)
from app.api.esquemas_cuentas import RespuestaCuentaCreada
from app.compartido.configuracion import obtener_configuracion
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.integracion.atencion_hospitalaria import (
    VIA_ARCHIVO,
    ErrorAtencionInvalida,
    ErrorAtencionNoEncontrada,
    ErrorAtencionYaImportada,
    ErrorSistemaHospitalarioNoDisponible,
    FuenteAtenciones,
)
from app.dominio.integracion.casos_uso_importacion import (
    ImportarAtencion,
    ImportarAtencionDelSistema,
    ListarAtencionesHospitalarias,
)
from app.dominio.integracion.copago_cobrado import (
    ConsultarCopagoCobrado,
    ErrorCopagoCobrado,
    ErrorCopagoInvalido,
    ErrorCopagoYaRegistrado,
    ErrorCuentaCerradaCopago,
    RegistrarCopagoCobrado,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.montos_comprobante_sql import copago_asegurado_de_cuenta
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_importacion_atencion_sql import (
    RepositorioImportacionAtencionSql,
)
from app.infraestructura.persistencia.repositorio_por_codificar_sql import (
    RepositorioCopagoCobradoSql,
)
from app.infraestructura.sistema_hospitalario.esquema_atencion import AtencionJson
from app.infraestructura.sistema_hospitalario.fuente_atenciones_http import (
    FuenteAtencionesHttp,
)

router = APIRouter(tags=["atenciones hospitalarias"])
_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)


def obtener_fuente_atenciones() -> FuenteAtenciones:
    configuracion = obtener_configuracion()
    return FuenteAtencionesHttp(
        configuracion.sistema_hospitalario_url_base, configuracion.sistema_hospitalario_clave
    )


def construir_importar_atencion(sesion: AsyncSession = Depends(obtener_sesion)) -> ImportarAtencion:
    return ImportarAtencion(RepositorioImportacionAtencionSql(sesion), RegistroEventosSql(sesion))


def _error_http(error: Exception) -> ErrorAplicacion:
    if isinstance(error, ErrorSistemaHospitalarioNoDisponible):
        return ErrorAplicacion(
            "SISTEMA_HOSPITALARIO_NO_DISPONIBLE",
            str(error),
            estado_http=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(error, ErrorAtencionYaImportada):
        return ErrorAplicacion(
            "ATENCION_YA_IMPORTADA",
            str(error),
            estado_http=status.HTTP_409_CONFLICT,
            detalles={"cuenta_id": error.cuenta_id},
        )
    if isinstance(error, ErrorAtencionNoEncontrada):
        return ErrorAplicacion(
            "ATENCION_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        )
    assert isinstance(error, ErrorAtencionInvalida)
    return ErrorAplicacion(error.codigo, str(error), estado_http=422)


_ERRORES_IMPORTACION = (
    ErrorSistemaHospitalarioNoDisponible,
    ErrorAtencionYaImportada,
    ErrorAtencionNoEncontrada,
    ErrorAtencionInvalida,
)


@router.get("/atenciones-hospitalarias", response_model=list[ResumenAtencionRespuesta])
async def listar_atenciones_hospitalarias(
    documento: str | None = None,
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
    fuente: FuenteAtenciones = Depends(obtener_fuente_atenciones),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> list[ResumenAtencionRespuesta]:
    """Las atenciones cerradas que aun no se importaron."""
    caso_uso = ListarAtencionesHospitalarias(fuente, RepositorioImportacionAtencionSql(sesion))
    try:
        atenciones = await caso_uso.ejecutar(documento)
    except ErrorSistemaHospitalarioNoDisponible as error:
        raise _error_http(error) from error
    return [ResumenAtencionRespuesta.desde_valor(a) for a in atenciones]


@router.post(
    "/atenciones-hospitalarias/{atencion_id}/importar",
    response_model=RespuestaCuentaCreada,
    status_code=status.HTTP_201_CREATED,
)
async def importar_atencion_por_consulta(
    atencion_id: str,
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
    fuente: FuenteAtenciones = Depends(obtener_fuente_atenciones),
    importar: ImportarAtencion = Depends(construir_importar_atencion),
) -> RespuestaCuentaCreada:
    try:
        cuenta_id = await ImportarAtencionDelSistema(fuente, importar).ejecutar(
            atencion_id, actor.nombre_usuario
        )
    except _ERRORES_IMPORTACION as error:
        raise _error_http(error) from error
    return RespuestaCuentaCreada(cuenta_id=cuenta_id)


@router.post(
    "/cuentas/importar", response_model=RespuestaCuentaCreada, status_code=status.HTTP_201_CREATED
)
async def importar_atencion_por_archivo(
    atencion: AtencionJson,
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
    importar: ImportarAtencion = Depends(construir_importar_atencion),
) -> RespuestaCuentaCreada:
    """El cuerpo es el archivo exportado por el sistema hospitalario."""
    try:
        cuenta_id = await importar.ejecutar(atencion.a_valor(), VIA_ARCHIVO, actor.nombre_usuario)
    except _ERRORES_IMPORTACION as error:
        raise _error_http(error) from error
    return RespuestaCuentaCreada(cuenta_id=cuenta_id)


@router.get("/cuentas/{cuenta_id}/copago-cobrado", response_model=CopagoCobradoRespuesta | None)
async def consultar_copago_cobrado(
    cuenta_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> CopagoCobradoRespuesta | None:
    """El copago que la clinica ya cobro al paciente; `null` si no hay."""
    copago = await ConsultarCopagoCobrado(RepositorioCopagoCobradoSql(sesion)).ejecutar(cuenta_id)
    return CopagoCobradoRespuesta.desde_valor(copago) if copago else None


def _error_copago(error: ErrorCopagoCobrado) -> ErrorAplicacion:
    if isinstance(error, ErrorCopagoInvalido):
        return ErrorAplicacion("COPAGO_INVALIDO", str(error), estado_http=422)
    if isinstance(error, ErrorCopagoYaRegistrado):
        return ErrorAplicacion("COPAGO_YA_REGISTRADO", str(error), estado_http=409)
    if isinstance(error, ErrorCuentaCerradaCopago):
        return ErrorAplicacion("CUENTA_CERRADA", str(error), estado_http=409)
    return ErrorAplicacion("CUENTA_NO_ENCONTRADA", str(error), estado_http=404)


@router.post(
    "/cuentas/{cuenta_id}/copago-cobrado",
    response_model=CopagoCobradoRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_copago_cobrado(
    cuenta_id: int,
    solicitud: SolicitudCopagoCobrado,
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> CopagoCobradoRespuesta:
    """Registro manual del cobro, con la referencia del comprobante de caja."""
    caso_uso = RegistrarCopagoCobrado(
        RepositorioCopagoCobradoSql(sesion),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
        reloj,
    )
    try:
        copago = await caso_uso.ejecutar(cuenta_id, solicitud.a_valor(), actor.nombre_usuario)
    except ErrorCopagoCobrado as error:
        raise _error_copago(error) from error
    return CopagoCobradoRespuesta.desde_valor(copago)


@router.get("/cuentas/{cuenta_id}/copago-asegurado", response_model=CopagoAseguradoRespuesta)
async def consultar_copago_asegurado(
    cuenta_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> CopagoAseguradoRespuesta:
    """Lo que el calculo de montos atribuye al asegurado."""
    return CopagoAseguradoRespuesta(monto=await copago_asegurado_de_cuenta(sesion, cuenta_id))
