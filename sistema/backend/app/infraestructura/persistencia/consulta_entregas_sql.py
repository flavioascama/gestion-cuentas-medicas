"""Adaptador de ConsultaEntregas (2026-11-19): de cada observacion de la
cuenta que llego de la aseguradora, cuando se entrego la respuesta (en la
comunicacion) y que paso con sus trabajos de entrega (en la cola)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.comunicaciones.casos_uso import TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS
from app.dominio.observaciones.entrega import ConsultaEntregas, HechosEntrega
from app.infraestructura.persistencia.modelos_comunicaciones import ComunicacionIafasModelo
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo


class ConsultaEntregasSql(ConsultaEntregas):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def hechos(self, cuenta_medica_id: int) -> dict[int, HechosEntrega]:
        remitidas = await self._remitidas(cuenta_medica_id)
        if not remitidas:
            return {}
        ultimo: dict[int, str] = {}
        primero: dict[int, str | None] = {}
        for estado, carga in await self._trabajos(cuenta_medica_id):
            observacion_id = carga.get("observacion_id")
            if observacion_id is None:
                continue
            ultimo[int(observacion_id)] = estado
            primero.setdefault(int(observacion_id), carga.get("usuario_origen"))
        return {
            observacion_id: HechosEntrega(
                remitida_en=remitida_en,
                estado_ultimo_trabajo=ultimo.get(observacion_id),
                solicitada_por=primero.get(observacion_id),
            )
            for observacion_id, remitida_en in remitidas.items()
        }

    async def _remitidas(self, cuenta_medica_id: int) -> dict[int, datetime | None]:
        filas = await self._sesion.execute(
            sa.select(
                ComunicacionIafasModelo.observacion_id,
                ComunicacionIafasModelo.respuesta_remitida_en,
            ).where(
                ComunicacionIafasModelo.cuenta_medica_id == cuenta_medica_id,
                ComunicacionIafasModelo.observacion_id.is_not(None),
            )
        )
        return {int(fila[0]): fila[1] for fila in filas.all()}

    async def _trabajos(self, cuenta_medica_id: int) -> list[tuple[str, dict[str, Any]]]:
        # En orden de creacion: el primero lo pidio quien respondio.
        filas = await self._sesion.execute(
            sa.select(TrabajoModelo.estado, TrabajoModelo.carga_util)
            .where(
                TrabajoModelo.tipo == TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
                TrabajoModelo.carga_util["cuenta_medica_id"].as_integer() == cuenta_medica_id,
            )
            .order_by(TrabajoModelo.id)
        )
        return [(fila[0], fila[1] or {}) for fila in filas.all()]
