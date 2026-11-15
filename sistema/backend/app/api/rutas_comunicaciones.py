"""/comunicaciones-iafas (2026-11-13): lo que la IAFAS comunico por su
portal o por correo (conformidad, glosa, liquidacion, pago), como lo
registro el robot, y la revision a pedido de ambos canales."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

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

router = APIRouter(prefix="/comunicaciones-iafas", tags=["comunicaciones_iafas"])

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_REVISA = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE, NombreRol.TESORERIA)


@router.get("", response_model=list[ComunicacionIafasRespuesta])
async def listar_comunicaciones(
    cuenta_id: int | None = Query(default=None),
    caso_uso: ListarComunicacionesIafas = Depends(construir_listar_comunicaciones),
    _: CargaSesion = Depends(_LECTURA),
) -> list[ComunicacionIafasRespuesta]:
    registradas = await caso_uso.ejecutar(cuenta_id)
    return [ComunicacionIafasRespuesta.desde_valor(valor) for valor in registradas]


@router.post("/revision", response_model=RevisionSolicitada, status_code=status.HTTP_202_ACCEPTED)
async def solicitar_revision(
    caso_uso: SolicitarRevisionComunicaciones = Depends(construir_solicitar_revision),
    actor: CargaSesion = Depends(_REVISA),
) -> RevisionSolicitada:
    return RevisionSolicitada(trabajo_id=await caso_uso.ejecutar(actor.nombre_usuario))
