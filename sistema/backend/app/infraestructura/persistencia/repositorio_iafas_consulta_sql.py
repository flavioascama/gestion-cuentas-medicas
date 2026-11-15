"""Adaptador de RepositorioIafasConsulta (Fase 19, Seccion 11)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.puertos_consulta import RepositorioIafasConsulta, ResumenIafas
from app.infraestructura.persistencia.modelos_integracion import IafasModelo


class RepositorioIafasConsultaSql(RepositorioIafasConsulta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(self) -> list[ResumenIafas]:
        resultado = await self._sesion.execute(sa.select(IafasModelo).order_by(IafasModelo.codigo))
        return [
            ResumenIafas(id=m.id, codigo=m.codigo, razon_social=m.razon_social)
            for m in resultado.scalars().all()
        ]
