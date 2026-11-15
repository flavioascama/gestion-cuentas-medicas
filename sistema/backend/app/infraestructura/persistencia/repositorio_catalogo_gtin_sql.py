"""Adaptador de RepositorioCatalogoGtin (Fase 19)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dominio.farmacia.dispensacion import ProductoCatalogo
from app.dominio.farmacia.puertos import (
    RepositorioCatalogoGtin,
    RepositorioProductosCatalogoGtin,
    VersionCatalogoGtin,
)
from app.infraestructura.persistencia.modelos_catalogo_gtin import (
    CatalogoGtinProductoModelo,
    CatalogoGtinVersionModelo,
)
from app.infraestructura.persistencia.repositorio_dispensacion_sql import a_producto_catalogo


class RepositorioCatalogoGtinSql(RepositorioCatalogoGtin, RepositorioProductosCatalogoGtin):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar_versiones(self) -> list[VersionCatalogoGtin]:
        resultado = await self._sesion.execute(
            sa.select(CatalogoGtinVersionModelo)
            .options(selectinload(CatalogoGtinVersionModelo.productos))
            .order_by(CatalogoGtinVersionModelo.id.desc())
        )
        return [
            VersionCatalogoGtin(
                id=m.id, ruta_origen=m.ruta_origen, conteo=len(m.productos), cargado_en=m.cargado_en
            )
            for m in resultado.scalars().all()
        ]

    async def productos_de_version(self, version_id: int) -> list[ProductoCatalogo]:
        filas = await self._sesion.execute(
            sa.select(CatalogoGtinProductoModelo)
            .where(CatalogoGtinProductoModelo.version_id == version_id)
            .order_by(CatalogoGtinProductoModelo.nombre)
        )
        return [a_producto_catalogo(fila) for fila in filas.scalars().all()]
