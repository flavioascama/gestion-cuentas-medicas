"""Adaptador de RepositorioConformidadAuditoria (CU-07): la conformidad
vigente es el ultimo evento AUDITORIA_CONFORME de la cuenta registrado
desde que la cuenta entro a su estado actual."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.dominio.observaciones.conformidad import (
    TIPO_EVENTO_CONFORMIDAD,
    RepositorioConformidadAuditoria,
)
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, EventoModelo


def entrada_al_estado_actual(cuenta_id_col: Any) -> ColumnElement[Any]:
    """Instante del ultimo evento de la cuenta que la dejo en su estado
    actual (mismo criterio que el control de plazos)."""
    evento = aliased(EventoModelo)
    return (
        sa.select(sa.func.max(evento.ocurrido_en))
        .where(
            evento.cuenta_medica_id == cuenta_id_col,
            evento.estado_nuevo == CuentaMedicaModelo.estado,
        )
        .scalar_subquery()
    )


def conformidad_desde(cuenta_id_col: Any, desde_col: Any) -> ColumnElement[bool]:
    evento = aliased(EventoModelo)
    return (
        sa.select(sa.literal(1))
        .where(
            evento.cuenta_medica_id == cuenta_id_col,
            evento.tipo_evento == TIPO_EVENTO_CONFORMIDAD,
            evento.ocurrido_en >= desde_col,
        )
        .exists()
    )


class RepositorioConformidadAuditoriaSql(RepositorioConformidadAuditoria):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def conformidad_vigente(self, cuenta_medica_id: int) -> datetime | None:
        desde = entrada_al_estado_actual(CuentaMedicaModelo.id)
        evento = aliased(EventoModelo)
        resultado = await self._sesion.execute(
            sa.select(sa.func.max(evento.ocurrido_en))
            .select_from(CuentaMedicaModelo)
            .join(evento, evento.cuenta_medica_id == CuentaMedicaModelo.id)
            .where(
                CuentaMedicaModelo.id == cuenta_medica_id,
                evento.tipo_evento == TIPO_EVENTO_CONFORMIDAD,
                evento.ocurrido_en >= desde,
            )
        )
        return resultado.scalar_one_or_none()
