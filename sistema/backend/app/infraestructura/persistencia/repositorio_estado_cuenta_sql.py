"""Adaptador de RepositorioEstadoCuenta (Seccion 5.2.4): compartido por
todos los casos de uso del motor de orquestacion que necesitan leer o
fijar `cuenta_medica.estado` tras una transicion ya validada."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo


class RepositorioEstadoCuentaSql(RepositorioEstadoCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return (
            await self._sesion.execute(
                sa.select(CuentaMedicaModelo.estado).where(
                    CuentaMedicaModelo.id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        await self._sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_medica_id)
            .values(estado=estado_nuevo)
        )
