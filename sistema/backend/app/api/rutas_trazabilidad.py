"""CU-14 (historial), CU-15 (indicadores del ciclo) y CU-16 (expediente
de auditoria), Seccion 6.2, Fase 29. El historial y el expediente son
exclusivos del jefe de cuentas medicas (Tabla 52/53: "permiso exclusivo
de exportacion" para el expediente, y es el mismo rol quien consulta el
historial); los indicadores son del jefe de cuentas medicas y del
gerente administrativo (Tabla 46: la unica operacion de la matriz con
mas de un "Si" fuera de "consultar las cuentas y su detalle")."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.dependencias_trazabilidad import (
    construir_consultar_historial_cuenta,
    construir_consultar_historial_lote,
    construir_exportar_expediente,
    construir_visualizar_indicadores_ciclo,
)
from app.api.esquemas_trazabilidad import (
    ExpedienteRespuesta,
    HistorialCuentaRespuesta,
    HistorialLoteRespuesta,
    IndicadoresCicloRespuesta,
    SolicitudExportacionExpediente,
)
from app.api.nombres_actores import con_nombres_en_historial
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.trazabilidad.casos_uso import (
    ConsultarHistorialCuenta,
    ConsultarHistorialLote,
    ExportarExpediente,
    VisualizarIndicadoresCiclo,
)
from app.dominio.trazabilidad.errores import ErrorCuentaInexistente, ErrorLoteInexistente
from app.dominio.trazabilidad.valores import FiltroIndicadores
from app.infraestructura.persistencia.base import obtener_sesion

router = APIRouter(prefix="/cuentas/{cuenta_id}", tags=["trazabilidad"])
router_indicadores = APIRouter(tags=["trazabilidad"])
router_historial_lote = APIRouter(prefix="/lotes/{lote_id}", tags=["trazabilidad"])

_SOLO_JEFE = requiere_rol(NombreRol.JEFE)
_INDICADORES = requiere_rol(NombreRol.JEFE, NombreRol.GERENTE)


@router.get("/historial", response_model=HistorialCuentaRespuesta)
async def consultar_historial_cuenta(
    cuenta_id: int,
    caso_uso: ConsultarHistorialCuenta = Depends(construir_consultar_historial_cuenta),
    actor: CargaSesion = Depends(_SOLO_JEFE),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> HistorialCuentaRespuesta:
    try:
        historial = await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except ErrorCuentaInexistente as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    respuesta = HistorialCuentaRespuesta.desde_valor(historial)
    await con_nombres_en_historial(sesion, respuesta)
    return respuesta


@router_historial_lote.get("/historial", response_model=HistorialLoteRespuesta)
async def consultar_historial_lote(
    lote_id: int,
    caso_uso: ConsultarHistorialLote = Depends(construir_consultar_historial_lote),
    actor: CargaSesion = Depends(_SOLO_JEFE),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> HistorialLoteRespuesta:
    """RT-13: el historial de cualquier lote, como el de la cuenta."""
    try:
        historial = await caso_uso.ejecutar(lote_id, actor.nombre_usuario)
    except ErrorLoteInexistente as error:
        raise ErrorAplicacion(
            "LOTE_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    respuesta = HistorialLoteRespuesta.desde_valor(historial)
    await con_nombres_en_historial(sesion, respuesta)
    return respuesta


@router.post("/expediente", response_model=ExpedienteRespuesta, status_code=status.HTTP_201_CREATED)
async def exportar_expediente(
    cuenta_id: int,
    solicitud: SolicitudExportacionExpediente,
    caso_uso: ExportarExpediente = Depends(construir_exportar_expediente),
    actor: CargaSesion = Depends(_SOLO_JEFE),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> ExpedienteRespuesta:
    try:
        expediente = await caso_uso.ejecutar(cuenta_id, solicitud.motivo, actor.nombre_usuario)
    except ErrorCuentaInexistente as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    respuesta = ExpedienteRespuesta.desde_valor(expediente)
    await con_nombres_en_historial(sesion, respuesta.historial)
    return respuesta


@router_indicadores.get("/indicadores", response_model=IndicadoresCicloRespuesta)
async def visualizar_indicadores_ciclo(
    iafas_codigo: str | None = None,
    periodo: str | None = None,
    caso_uso: VisualizarIndicadoresCiclo = Depends(construir_visualizar_indicadores_ciclo),
    _actor: CargaSesion = Depends(_INDICADORES),
) -> IndicadoresCicloRespuesta:
    indicadores = await caso_uso.ejecutar(
        FiltroIndicadores(iafas_codigo=iafas_codigo, periodo=periodo)
    )
    return IndicadoresCicloRespuesta.desde_valor(indicadores)
