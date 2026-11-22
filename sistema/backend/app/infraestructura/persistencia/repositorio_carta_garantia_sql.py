"""Adaptador de RepositorioCartaGarantia (RF-13)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acreditacion.carta_garantia import CartaGarantia, RepositorioCartaGarantia
from app.infraestructura.persistencia.modelos_carta_garantia import CartaGarantiaModelo


class RepositorioCartaGarantiaSql(RepositorioCartaGarantia):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener(self, cuenta_medica_id: int) -> CartaGarantia | None:
        fila = (
            await self._sesion.execute(
                sa.select(CartaGarantiaModelo).where(
                    CartaGarantiaModelo.cuenta_medica_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()
        if fila is None:
            return None
        return CartaGarantia(
            cuenta_medica_id=fila.cuenta_medica_id,
            numero=fila.numero,
            vigente_desde=fila.vigente_desde,
            vigente_hasta=fila.vigente_hasta,
            monto=fila.monto,
            registrado_en=fila.registrado_en,
            registrado_por=fila.registrado_por,
        )

    async def guardar(self, carta: CartaGarantia) -> None:
        self._sesion.add(
            CartaGarantiaModelo(
                cuenta_medica_id=carta.cuenta_medica_id,
                numero=carta.numero,
                vigente_desde=carta.vigente_desde,
                vigente_hasta=carta.vigente_hasta,
                monto=carta.monto,
                registrado_en=carta.registrado_en,
                registrado_por=carta.registrado_por,
            )
        )
        await self._sesion.flush()

    async def actualizar(self, carta: CartaGarantia) -> None:
        await self._sesion.execute(
            sa.update(CartaGarantiaModelo)
            .where(CartaGarantiaModelo.cuenta_medica_id == carta.cuenta_medica_id)
            .values(
                numero=carta.numero,
                vigente_desde=carta.vigente_desde,
                vigente_hasta=carta.vigente_hasta,
                monto=carta.monto,
            )
        )
        await self._sesion.flush()
