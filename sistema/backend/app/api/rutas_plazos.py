"""RNF-06: el vencimiento vigente de cada cuenta, para mostrarlo junto a su
estado en la bandeja y en el detalle. Mismos roles que consultan cuentas
(Tabla 46)."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.serializacion import campos
from app.compartido.configuracion import obtener_configuracion
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.plazos.consulta import ConsultarVencimientos, Vencimiento
from app.dominio.plazos.declaracion_susalud import (
    ErrorDeclaracionSusalud,
    ErrorPeriodoConLotes,
    ErrorPeriodoInvalido,
    ErrorPeriodoNoCerrado,
    RegistrarDeclaracionSinFacturacion,
)
from app.dominio.plazos.susalud import ConsultarControlSusalud, ControlPeriodoSusalud
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_control_susalud_sql import (
    RepositorioControlSusaludSql,
)
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql

router = APIRouter(prefix="/plazos", tags=["plazos"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
# El envio a SUSALUD lo pide el analista (Fase 18); el jefe consulta los lotes.
_LECTURA_SUSALUD = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)
_ESCRITURA_SUSALUD = requiere_rol(NombreRol.ANALISTA)


class VencimientoRespuesta(BaseModel):
    cuenta_medica_id: int
    hito: str
    vence_en: datetime
    vencido: bool
    por_vencer: bool

    @staticmethod
    def desde_valor(valor: Vencimiento) -> VencimientoRespuesta:
        return VencimientoRespuesta(**campos(valor))


def construir_consultar_vencimientos(
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
) -> ConsultarVencimientos:
    configuracion = obtener_configuracion()
    return ConsultarVencimientos(
        RepositorioPlazosSql(sesion, configuracion.dias_plazo_reenvio_lote_rechazado),
        reloj,
        configuracion.dias_aviso_previo_vencimiento,
    )


@router.get("/vencimientos", response_model=list[VencimientoRespuesta])
async def listar_vencimientos(
    caso_uso: ConsultarVencimientos = Depends(construir_consultar_vencimientos),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[VencimientoRespuesta]:
    return [VencimientoRespuesta.desde_valor(v) for v in await caso_uso.ejecutar()]


class ControlPeriodoSusaludRespuesta(BaseModel):
    periodo: str
    lotes: int
    pendientes_envio: int
    fecha_limite: date
    ultimo_envio: datetime | None
    estado: str
    listos_envio: int
    declarada_en: datetime | None

    @staticmethod
    def desde_valor(valor: ControlPeriodoSusalud) -> ControlPeriodoSusaludRespuesta:
        return ControlPeriodoSusaludRespuesta(**campos(valor))


def construir_consultar_control_susalud(
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
) -> ConsultarControlSusalud:
    configuracion = obtener_configuracion()
    return ConsultarControlSusalud(
        RepositorioControlSusaludSql(sesion),
        reloj,
        configuracion.conjunto_feriados,
        configuracion.dias_aviso_previo_vencimiento,
    )


@router.get("/susalud", response_model=list[ControlPeriodoSusaludRespuesta])
async def control_envio_susalud(
    caso_uso: ConsultarControlSusalud = Depends(construir_consultar_control_susalud),
    _actor: CargaSesion = Depends(_LECTURA_SUSALUD),
) -> list[ControlPeriodoSusaludRespuesta]:
    """RT-05 y RI-16: plazo de los diez dias habiles y meses sin lotes."""
    return [ControlPeriodoSusaludRespuesta.desde_valor(c) for c in await caso_uso.ejecutar()]


class SolicitudDeclaracionSinFacturacion(BaseModel):
    periodo: str = Field(pattern=r"^\d{6}$")


class DeclaracionSinFacturacionRespuesta(BaseModel):
    periodo: str
    registrada_en: datetime


def construir_registrar_declaracion(
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarDeclaracionSinFacturacion:
    return RegistrarDeclaracionSinFacturacion(
        RepositorioControlSusaludSql(sesion), RegistroEventosSql(sesion), reloj
    )


def _error_declaracion(error: ErrorDeclaracionSusalud) -> ErrorAplicacion:
    if isinstance(error, ErrorPeriodoInvalido):
        return ErrorAplicacion("PERIODO_INVALIDO", str(error), estado_http=400)
    if isinstance(error, ErrorPeriodoNoCerrado):
        return ErrorAplicacion("PERIODO_NO_CERRADO", str(error), estado_http=409)
    if isinstance(error, ErrorPeriodoConLotes):
        return ErrorAplicacion("PERIODO_CON_LOTES", str(error), estado_http=409)
    return ErrorAplicacion("PERIODO_YA_DECLARADO", str(error), estado_http=409)


@router.post(
    "/susalud/declaraciones",
    response_model=DeclaracionSinFacturacionRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_declaracion_sin_facturacion(
    solicitud: SolicitudDeclaracionSinFacturacion,
    caso_uso: RegistrarDeclaracionSinFacturacion = Depends(construir_registrar_declaracion),
    actor: CargaSesion = Depends(_ESCRITURA_SUSALUD),
) -> DeclaracionSinFacturacionRespuesta:
    """Constancia de la declaracion jurada de un mes sin lotes que reportar."""
    try:
        registrada_en = await caso_uso.ejecutar(
            solicitud.periodo, actor.nombre_usuario, actor.usuario_id
        )
    except ErrorDeclaracionSusalud as error:
        raise _error_declaracion(error) from error
    return DeclaracionSinFacturacionRespuesta(
        periodo=solicitud.periodo, registrada_en=registrada_en
    )
