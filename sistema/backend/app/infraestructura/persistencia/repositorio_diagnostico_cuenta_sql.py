"""Adaptador de RepositorioDiagnosticoCuenta."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.diagnostico_cuenta import RepositorioDiagnosticoCuenta
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo


class RepositorioDiagnosticoCuentaSql(RepositorioDiagnosticoCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def estado_y_diagnostico(self, cuenta_id: int) -> tuple[str, str | None] | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            return None
        return cuenta.estado, cuenta.diagnostico_principal_cie10

    async def existe_cie10(self, codigo: str) -> bool:
        encontrado = await self._sesion.scalar(
            sa.select(sa.literal(True))
            .select_from(Cie10CodigoModelo)
            .where(Cie10CodigoModelo.codigo == codigo)
            .limit(1)
        )
        return bool(encontrado)

    async def fijar_diagnostico(self, cuenta_id: int, codigo: str) -> None:
        await self._sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_id)
            .values(diagnostico_principal_cie10=codigo)
        )
        await self._sesion.flush()
