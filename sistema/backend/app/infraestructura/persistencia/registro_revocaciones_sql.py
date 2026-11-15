"""Adaptador del puerto RegistroRevocaciones (control C-01, Seccion 5.2.7:
lista de revocacion de credenciales de sesion)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.puertos import RegistroRevocaciones
from app.infraestructura.persistencia.modelos_acceso import TokenRevocadoModelo


class RegistroRevocacionesSql(RegistroRevocaciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def revocar(self, jti: str, expira_en: datetime) -> None:
        self._sesion.add(TokenRevocadoModelo(jti=jti, expira_en=expira_en))
        try:
            await self._sesion.commit()
        except IntegrityError:
            # Cerrar sesion dos veces con el mismo token (doble clic, un
            # reintento de red) no es un error: el token ya esta revocado,
            # que es exactamente lo que se pedia.
            await self._sesion.rollback()

    async def esta_revocado(self, jti: str) -> bool:
        resultado = await self._sesion.execute(
            sa.select(TokenRevocadoModelo.jti).where(TokenRevocadoModelo.jti == jti)
        )
        return resultado.scalar_one_or_none() is not None
