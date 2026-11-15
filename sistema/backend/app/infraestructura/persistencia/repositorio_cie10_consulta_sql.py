"""Adaptador de RepositorioCie10Consulta: buscador del campo "Diagnostico
principal (CIE-10)" del formulario de nueva cuenta."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.puertos_consulta import RepositorioCie10Consulta, ResumenCie10
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo


class RepositorioCie10ConsultaSql(RepositorioCie10Consulta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def buscar(self, texto: str, limite: int) -> list[ResumenCie10]:
        version_id = await self._sesion.scalar(sa.select(sa.func.max(Cie10VersionModelo.id)))
        if version_id is None:
            return []

        patron = f"%{texto}%"
        consulta = (
            sa.select(Cie10CodigoModelo)
            .where(
                Cie10CodigoModelo.cie10_version_id == version_id,
                sa.or_(
                    Cie10CodigoModelo.codigo.ilike(patron),
                    Cie10CodigoModelo.descripcion.ilike(patron),
                ),
            )
            .order_by(Cie10CodigoModelo.codigo)
            .limit(limite)
        )
        resultado = await self._sesion.execute(consulta)
        return [
            ResumenCie10(codigo=m.codigo, descripcion=m.descripcion)
            for m in resultado.scalars().all()
        ]
