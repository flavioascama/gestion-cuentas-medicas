"""RNF-06: el vencimiento vigente de cada cuenta, para mostrarlo junto a su
estado en la bandeja y en el detalle. Mismos roles que consultan cuentas
(Tabla 46)."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.serializacion import campos
from app.compartido.configuracion import obtener_configuracion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.plazos.consulta import ConsultarVencimientos, Vencimiento
from app.dominio.plazos.susalud import ConsultarControlSusalud, ControlPeriodoSusalud
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_control_susalud_sql import (
    RepositorioControlSusaludSql,
)
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql

router = APIRouter(prefix="/plazos", tags=["plazos"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
# El envio a SUSALUD lo pide el analista (Fase 18); el jefe consulta los lotes.
_LECTURA_SUSALUD = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)


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
