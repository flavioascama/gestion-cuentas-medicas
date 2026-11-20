"""Adaptadores de RepositorioProcedimientosPorCodificar y de
RepositorioCopagoCobrado (atencion importada del sistema hospitalario,
2026-11-19)."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.cpms.por_codificar import (
    ProcedimientoPorCodificar,
    RepositorioProcedimientosPorCodificar,
)
from app.dominio.integracion.copago_cobrado import CopagoCobrado, RepositorioCopagoCobrado
from app.infraestructura.persistencia.modelos_atencion_hospitalaria import (
    CopagoCobradoModelo,
    ProcedimientoPorCodificarModelo,
)
from app.infraestructura.persistencia.modelos_carta_garantia import CartaGarantiaModelo


def _pendientes(cuenta_medica_id: int) -> sa.ColumnElement[bool]:
    return sa.and_(
        ProcedimientoPorCodificarModelo.cuenta_medica_id == cuenta_medica_id,
        ProcedimientoPorCodificarModelo.procedimiento_facturado_id.is_(None),
    )


async def contar_por_codificar(sesion: AsyncSession, cuenta_medica_id: int) -> int:
    cantidad = await sesion.scalar(
        sa.select(sa.func.count())
        .select_from(ProcedimientoPorCodificarModelo)
        .where(_pendientes(cuenta_medica_id))
    )
    return int(cantidad or 0)


async def tiene_carta_garantia(sesion: AsyncSession, cuenta_medica_id: int) -> bool:
    encontrada = await sesion.scalar(
        sa.select(sa.literal(True))
        .select_from(CartaGarantiaModelo)
        .where(CartaGarantiaModelo.cuenta_medica_id == cuenta_medica_id)
        .limit(1)
    )
    return bool(encontrada)


class RepositorioProcedimientosPorCodificarSql(RepositorioProcedimientosPorCodificar):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar_pendientes(self, cuenta_medica_id: int) -> list[ProcedimientoPorCodificar]:
        filas = await self._sesion.execute(
            sa.select(ProcedimientoPorCodificarModelo)
            .where(_pendientes(cuenta_medica_id))
            .order_by(ProcedimientoPorCodificarModelo.id)
        )
        return [
            ProcedimientoPorCodificar(
                id=fila.id,
                descripcion=fila.descripcion,
                area=fila.area,
                cantidad=fila.cantidad,
                monto_unitario=fila.monto_unitario,
                fecha=fila.fecha,
            )
            for fila in filas.scalars().all()
        ]


class RepositorioCopagoCobradoSql(RepositorioCopagoCobrado):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener(self, cuenta_medica_id: int) -> CopagoCobrado | None:
        fila = await self._sesion.scalar(
            sa.select(CopagoCobradoModelo).where(
                CopagoCobradoModelo.cuenta_medica_id == cuenta_medica_id
            )
        )
        if fila is None:
            return None
        return CopagoCobrado(
            monto=fila.monto,
            fecha=fila.fecha,
            referencia=fila.referencia,
            origen=fila.origen,
            registrado_por=fila.registrado_por,
            registrado_en=fila.registrado_en,
        )

    async def registrar(self, cuenta_medica_id: int, copago: CopagoCobrado) -> int:
        fila = CopagoCobradoModelo(
            cuenta_medica_id=cuenta_medica_id,
            monto=copago.monto,
            fecha=copago.fecha,
            referencia=copago.referencia,
            origen=copago.origen,
            registrado_por=copago.registrado_por,
            registrado_en=copago.registrado_en or datetime.now(UTC),
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        return fila.id
