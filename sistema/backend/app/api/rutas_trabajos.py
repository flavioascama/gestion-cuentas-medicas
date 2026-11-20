"""Seccion 11: `GET /trabajos/{id}`, solo analista, jefe y tesoreria: los
que lanzan tareas del robot desde las pantallas (Fase 18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import requiere_rol
from app.api.dependencias_cola import construir_obtener_trabajo
from app.api.esquemas_cola import DetalleTrabajoRespuesta
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.cola.casos_uso import ObtenerTrabajo

router = APIRouter(prefix="/trabajos", tags=["trabajos"])

_QUIENES_LANZAN_TAREAS = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE, NombreRol.TESORERIA)


@router.get("/{trabajo_id}", response_model=DetalleTrabajoRespuesta)
async def obtener_trabajo(
    trabajo_id: int,
    caso_uso: ObtenerTrabajo = Depends(construir_obtener_trabajo),
    _actor: CargaSesion = Depends(_QUIENES_LANZAN_TAREAS),
) -> DetalleTrabajoRespuesta:
    trabajo = await caso_uso.ejecutar(trabajo_id)
    if trabajo is None:
        raise ErrorAplicacion(
            "TRABAJO_NO_ENCONTRADO",
            f"No existe el trabajo {trabajo_id}.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return DetalleTrabajoRespuesta.desde_valor(trabajo)
