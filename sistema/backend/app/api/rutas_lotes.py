"""Seccion 11: /lotes. `POST /lotes`, `GET /lotes`, `GET /lotes/{id}`,
`GET /lotes/{id}/prevalidacion` y `GET /lotes/{id}/validacion-oficial`
para analista y jefe; `POST /lotes/{id}/carga-validador`, `POST
/lotes/{id}/remision-iafas`, `GET /lotes/{id}/acuses` y `POST
/lotes/envio-susalud` solo para analista (Fase 18)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from app.api.dependencias import requiere_rol
from app.api.dependencias_lotes import (
    construir_generar_lote,
    construir_listar_lotes,
    construir_obtener_acuses_lote,
    construir_obtener_cuentas_lote,
    construir_obtener_lote,
    construir_obtener_prevalidacion_lote,
    construir_obtener_ruta_s01_lote,
    construir_obtener_validacion_oficial_lote,
    construir_remitir_lote,
    construir_solicitar_carga_en_validador,
    construir_solicitar_envio_susalud,
)
from app.api.esquemas_lotes import (
    CuentaLoteRespuesta,
    DetalleLoteRespuesta,
    InformePrevalidacionRespuesta,
    RespuestaEnvioSusalud,
    RespuestaGenerarLote,
    RespuestaRemitirLote,
    RespuestaTrabajoEncolado,
    ResultadoValidacionOficialRespuesta,
    ResumenAcuseRespuesta,
    ResumenLoteRespuesta,
    SolicitudEnvioSusalud,
    SolicitudGenerarLote,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.integracion.casos_uso_consulta import (
    ListarLotes,
    ObtenerAcusesLote,
    ObtenerCuentasLote,
    ObtenerLote,
    ObtenerPrevalidacionLote,
    ObtenerRutaS01Lote,
    ObtenerValidacionOficialLote,
)
from app.dominio.integracion.casos_uso_validacion import (
    SolicitarCargaEnValidador,
    SolicitarEnvioSusalud,
)
from app.dominio.integracion.puertos import ErrorLoteNoRemisible, ErrorRepositorioLote
from app.dominio.integracion.puertos_validacion import ErrorLoteNoCargable
from app.infraestructura.tedef.generar_lote import GenerarLote
from app.infraestructura.tedef.remitir_lote import RemitirLote

router = APIRouter(prefix="/lotes", tags=["lotes"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)
_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)


@router.post("", response_model=RespuestaGenerarLote, status_code=status.HTTP_201_CREATED)
async def generar_lote(
    solicitud: SolicitudGenerarLote,
    caso_uso: GenerarLote = Depends(construir_generar_lote),
    actor: CargaSesion = Depends(_LECTURA),
) -> RespuestaGenerarLote:
    try:
        resultado = await caso_uso.ejecutar(
            solicitud.iafas_id, solicitud.periodo, solicitud.cuenta_ids, actor.nombre_usuario
        )
    except ErrorRepositorioLote as error:
        raise ErrorAplicacion(
            "LOTE_NO_GENERABLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaGenerarLote.desde_valor(resultado)


@router.get("", response_model=list[ResumenLoteRespuesta])
async def listar_lotes(
    periodo: str | None = None,
    estado: str | None = None,
    iafas_id: int | None = None,
    caso_uso: ListarLotes = Depends(construir_listar_lotes),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ResumenLoteRespuesta]:
    lotes = await caso_uso.ejecutar(periodo, estado, iafas_id)
    return [ResumenLoteRespuesta.desde_valor(lote) for lote in lotes]


@router.get("/{lote_id}", response_model=DetalleLoteRespuesta)
async def obtener_lote(
    lote_id: int,
    caso_uso: ObtenerLote = Depends(construir_obtener_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> DetalleLoteRespuesta:
    lote = await caso_uso.ejecutar(lote_id)
    if lote is None:
        raise ErrorAplicacion(
            "LOTE_NO_ENCONTRADO",
            f"No existe el lote {lote_id}.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return DetalleLoteRespuesta.desde_valor(lote)


@router.get("/{lote_id}/prevalidacion", response_model=InformePrevalidacionRespuesta)
async def obtener_prevalidacion_lote(
    lote_id: int,
    caso_uso: ObtenerPrevalidacionLote = Depends(construir_obtener_prevalidacion_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> InformePrevalidacionRespuesta:
    informe = await caso_uso.ejecutar(lote_id)
    if informe is None:
        raise ErrorAplicacion(
            "PREVALIDACION_NO_ENCONTRADA",
            f"El lote {lote_id} no tiene informe de prevalidacion persistido.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return InformePrevalidacionRespuesta.desde_valor(informe)


@router.post(
    "/{lote_id}/carga-validador",
    response_model=RespuestaTrabajoEncolado,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_carga_en_validador(
    lote_id: int,
    caso_uso: SolicitarCargaEnValidador = Depends(construir_solicitar_carga_en_validador),
    # Tabla 46: "Generar y validar el lote", analista y jefe (2026-11-13).
    actor: CargaSesion = Depends(_LECTURA),
) -> RespuestaTrabajoEncolado:
    try:
        trabajo_id = await caso_uso.ejecutar(lote_id, actor.nombre_usuario)
    except ErrorLoteNoCargable as error:
        raise ErrorAplicacion(
            "LOTE_NO_CARGABLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaTrabajoEncolado(trabajo_id=trabajo_id)


@router.get(
    "/{lote_id}/validacion-oficial", response_model=list[ResultadoValidacionOficialRespuesta]
)
async def obtener_validacion_oficial_lote(
    lote_id: int,
    caso_uso: ObtenerValidacionOficialLote = Depends(construir_obtener_validacion_oficial_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ResultadoValidacionOficialRespuesta]:
    resultados = await caso_uso.ejecutar(lote_id)
    return [ResultadoValidacionOficialRespuesta.desde_valor(r) for r in resultados]


@router.post(
    "/{lote_id}/remision-iafas",
    response_model=RespuestaRemitirLote,
    status_code=status.HTTP_201_CREATED,
)
async def remitir_lote(
    lote_id: int,
    caso_uso: RemitirLote = Depends(construir_remitir_lote),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaRemitirLote:
    try:
        resultado = await caso_uso.ejecutar(lote_id, actor.nombre_usuario)
    except ErrorLoteNoRemisible as error:
        raise ErrorAplicacion(
            "LOTE_NO_REMISIBLE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaRemitirLote.desde_valor(resultado)


# Tabla 46: el jefe consulta los lotes; antes los acuses eran solo del
# analista y el detalle del lote le mostraba "sin acuses" aunque existieran.
@router.get("/{lote_id}/acuses", response_model=list[ResumenAcuseRespuesta])
async def obtener_acuses_lote(
    lote_id: int,
    caso_uso: ObtenerAcusesLote = Depends(construir_obtener_acuses_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ResumenAcuseRespuesta]:
    acuses = await caso_uso.ejecutar(lote_id)
    return [ResumenAcuseRespuesta.desde_valor(a) for a in acuses]


@router.get("/{lote_id}/cuentas", response_model=list[CuentaLoteRespuesta])
async def obtener_cuentas_lote(
    lote_id: int,
    caso_uso: ObtenerCuentasLote = Depends(construir_obtener_cuentas_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[CuentaLoteRespuesta]:
    cuentas = await caso_uso.ejecutar(lote_id)
    return [CuentaLoteRespuesta.desde_valor(c) for c in cuentas]


@router.get("/{lote_id}/archivo-s01")
async def descargar_archivo_s01_lote(
    lote_id: int,
    caso_uso: ObtenerRutaS01Lote = Depends(construir_obtener_ruta_s01_lote),
    _actor: CargaSesion = Depends(_LECTURA),
) -> FileResponse:
    ruta = await caso_uso.ejecutar(lote_id)
    if ruta is None:
        raise ErrorAplicacion(
            "ARCHIVO_S01_NO_DISPONIBLE",
            f"El lote {lote_id} todavia no tiene un archivo .S01 obtenido del validador.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return FileResponse(ruta, filename=Path(ruta).name, media_type="application/octet-stream")


@router.post(
    "/envio-susalud",
    response_model=RespuestaEnvioSusalud,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_envio_susalud(
    solicitud: SolicitudEnvioSusalud,
    caso_uso: SolicitarEnvioSusalud = Depends(construir_solicitar_envio_susalud),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaEnvioSusalud:
    trabajo_id = await caso_uso.ejecutar(solicitud.periodo, actor.nombre_usuario)
    return RespuestaEnvioSusalud(trabajo_id=trabajo_id)
