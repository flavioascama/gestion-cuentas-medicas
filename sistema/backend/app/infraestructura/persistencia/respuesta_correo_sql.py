"""Respuestas de la clinica a un correo de la IAFAS: se guardan, se
encolan para el robot y se marcan cuando salieron."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.infraestructura.persistencia.modelos_correos import (
    CorreoIafasModelo,
    RespuestaCorreoIafasModelo,
)
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo

TIPO_TRABAJO_ENVIAR_RESPUESTA_CORREO = "ENVIAR_RESPUESTA_CORREO"


@dataclass(frozen=True, slots=True)
class RespuestaCorreo:
    id: int
    texto: str
    respondido_por: str
    respondido_en: datetime
    enviada_en: datetime | None


@dataclass(frozen=True, slots=True)
class EnvioPendiente:
    destinatario: str
    asunto: str
    texto: str


async def registrar_respuesta(sesion: AsyncSession, correo_id: int, texto: str, actor: str) -> None:
    """Guarda la respuesta y deja al robot el trabajo de enviarla."""
    ahora = datetime.now(UTC)
    fila = RespuestaCorreoIafasModelo(
        correo_id=correo_id, texto=texto, respondido_por=actor, respondido_en=ahora
    )
    sesion.add(fila)
    await sesion.flush()
    sesion.add(
        TrabajoModelo(
            tipo=TIPO_TRABAJO_ENVIAR_RESPUESTA_CORREO,
            carga_util={"respuesta_id": fila.id},
            proximo_intento=ahora,
        )
    )
    await sesion.commit()


async def listar_respuestas(sesion: AsyncSession, correo_id: int) -> list[RespuestaCorreo]:
    filas = await sesion.scalars(
        sa.select(RespuestaCorreoIafasModelo)
        .where(RespuestaCorreoIafasModelo.correo_id == correo_id)
        .order_by(RespuestaCorreoIafasModelo.id)
    )
    return [
        RespuestaCorreo(f.id, f.texto, f.respondido_por, f.respondido_en, f.enviada_en)
        for f in filas
    ]


async def envio_pendiente(sesion: AsyncSession, respuesta_id: int) -> EnvioPendiente | None:
    """Lo que falta enviar; None si la respuesta no existe o ya salio."""
    fila = (
        await sesion.execute(
            sa.select(RespuestaCorreoIafasModelo, CorreoIafasModelo)
            .join(CorreoIafasModelo, CorreoIafasModelo.id == RespuestaCorreoIafasModelo.correo_id)
            .where(
                RespuestaCorreoIafasModelo.id == respuesta_id,
                RespuestaCorreoIafasModelo.enviada_en.is_(None),
            )
        )
    ).first()
    if fila is None:
        return None
    respuesta, correo = fila
    return EnvioPendiente(correo.remitente, f"Re: {correo.asunto}", respuesta.texto)


async def marcar_enviada(sesion: AsyncSession, respuesta_id: int) -> None:
    await sesion.execute(
        sa.update(RespuestaCorreoIafasModelo)
        .where(RespuestaCorreoIafasModelo.id == respuesta_id)
        .values(enviada_en=datetime.now(UTC))
    )
    await sesion.commit()
