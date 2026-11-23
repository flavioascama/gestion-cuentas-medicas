"""El robot envia, desde el buzon de la clinica, la respuesta que una
persona escribio a un correo de la IAFAS (2026-11-22)."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from typing import TYPE_CHECKING

import structlog
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.respuesta_correo_sql import (
    EnvioPendiente,
    envio_pendiente,
    marcar_enviada,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trabajador.configuracion import configuracion

if TYPE_CHECKING:
    from app.dominio.puertos_comunes import TrabajoPendiente

    from trabajador.manejadores import Adaptadores

registro = structlog.get_logger(__name__)


def _enviar(envio: EnvioPendiente) -> None:
    mensaje = EmailMessage()
    mensaje["Subject"] = envio.asunto
    mensaje["From"] = configuracion.correo_imap_usuario
    mensaje["To"] = envio.destinatario
    mensaje["Date"] = formatdate(localtime=True)
    mensaje.set_content(envio.texto)
    with smtplib.SMTP(
        configuracion.correo_smtp_host, configuracion.correo_smtp_puerto, timeout=20
    ) as cliente:
        if configuracion.correo_imap_tls:
            cliente.starttls()
            cliente.login(configuracion.correo_imap_usuario, configuracion.correo_imap_clave)
        cliente.send_message(mensaje)


async def procesar_enviar_respuesta_correo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    """Si el envio falla, la excepcion deja el trabajo para reintento."""
    del adaptadores
    respuesta_id = trabajo.carga_util["respuesta_id"]
    async with fabrica_sesiones() as sesion:
        envio = await envio_pendiente(sesion, respuesta_id)
        if envio is not None:
            await asyncio.to_thread(_enviar, envio)
            await marcar_enviada(sesion, respuesta_id)
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)
    registro.info("respuesta_correo_enviada", trabajo_id=trabajo.id, respuesta_id=respuesta_id)
