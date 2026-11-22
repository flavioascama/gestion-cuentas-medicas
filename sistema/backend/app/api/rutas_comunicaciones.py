"""/comunicaciones-iafas (2026-11-13): lo que la IAFAS comunico por su
portal o por correo (conformidad, glosa, liquidacion, pago), como lo
registro el robot, y la revision a pedido de ambos canales."""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.dependencias_comunicaciones import (
    construir_listar_comunicaciones,
    construir_solicitar_revision,
)
from app.api.esquemas_comunicaciones import ComunicacionIafasRespuesta, RevisionSolicitada
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.casos_uso import (
    ListarComunicacionesIafas,
    SolicitarRevisionComunicaciones,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo

router = APIRouter(prefix="/comunicaciones-iafas", tags=["comunicaciones_iafas"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_REVISA = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE, NombreRol.TESORERIA)


@router.get("", response_model=list[ComunicacionIafasRespuesta])
async def listar_comunicaciones(
    cuenta_id: int | None = Query(default=None),
    caso_uso: ListarComunicacionesIafas = Depends(construir_listar_comunicaciones),
    _: CargaSesion = Depends(_LECTURA),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> list[ComunicacionIafasRespuesta]:
    respuestas = [
        ComunicacionIafasRespuesta.desde_valor(v) for v in await caso_uso.ejecutar(cuenta_id)
    ]
    await _con_identificacion_de_cuenta(sesion, respuestas)
    return respuestas


async def _con_identificacion_de_cuenta(
    sesion: AsyncSession, respuestas: list[ComunicacionIafasRespuesta]
) -> None:
    """Una sola consulta para todas las cuentas de la lista."""
    ids = {r.cuenta_medica_id for r in respuestas if r.cuenta_medica_id is not None}
    if not ids:
        return
    filas = await sesion.execute(
        sa.select(CuentaMedicaModelo.id, CuentaMedicaModelo.identificacion_interna).where(
            CuentaMedicaModelo.id.in_(ids)
        )
    )
    identificaciones = dict(filas.tuples().all())
    for respuesta in respuestas:
        if respuesta.cuenta_medica_id is not None:
            respuesta.identificacion_interna = identificaciones.get(respuesta.cuenta_medica_id)


@router.post("/revision", response_model=RevisionSolicitada, status_code=status.HTTP_202_ACCEPTED)
async def solicitar_revision(
    caso_uso: SolicitarRevisionComunicaciones = Depends(construir_solicitar_revision),
    actor: CargaSesion = Depends(_REVISA),
) -> RevisionSolicitada:
    return RevisionSolicitada(trabajo_id=await caso_uso.ejecutar(actor.nombre_usuario))
