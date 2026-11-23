"""Guarda y lee el PDF adjunto a la respuesta de una observacion."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.observaciones.adjunto_respuesta import AdjuntoRespuesta, ErrorAdjuntoNoValido
from app.infraestructura.persistencia.modelos_observaciones import (
    AdjuntoRespuestaObservacionModelo,
    ObservacionModelo,
)


async def guardar_adjunto(
    sesion: AsyncSession,
    observacion_id: int,
    adjunto: AdjuntoRespuesta,
    actor: str,
) -> None:
    """Reemplaza el adjunto anterior, si lo hay; solo mientras la
    observacion sigue sin responder."""
    estado = await sesion.scalar(
        sa.select(ObservacionModelo.estado).where(ObservacionModelo.id == observacion_id)
    )
    if estado != "ABIERTA":
        raise ErrorAdjuntoNoValido("La observación no admite un documento adjunto.")
    await sesion.execute(
        sa.delete(AdjuntoRespuestaObservacionModelo).where(
            AdjuntoRespuestaObservacionModelo.observacion_id == observacion_id
        )
    )
    sesion.add(
        AdjuntoRespuestaObservacionModelo(
            observacion_id=observacion_id,
            nombre=adjunto.nombre,
            tamano=len(adjunto.contenido),
            contenido=adjunto.contenido,
            subido_por=actor,
            subido_en=datetime.now(UTC),
        )
    )
    await sesion.commit()


async def obtener_adjunto(sesion: AsyncSession, observacion_id: int) -> AdjuntoRespuesta | None:
    fila = await sesion.scalar(
        sa.select(AdjuntoRespuestaObservacionModelo).where(
            AdjuntoRespuestaObservacionModelo.observacion_id == observacion_id
        )
    )
    return None if fila is None else AdjuntoRespuesta(fila.nombre, fila.contenido)


async def nombres_de_adjuntos(sesion: AsyncSession, observacion_ids: list[int]) -> dict[int, str]:
    if not observacion_ids:
        return {}
    filas = await sesion.scalars(
        sa.select(AdjuntoRespuestaObservacionModelo).where(
            AdjuntoRespuestaObservacionModelo.observacion_id.in_(observacion_ids)
        )
    )
    return {fila.observacion_id: fila.nombre for fila in filas}
