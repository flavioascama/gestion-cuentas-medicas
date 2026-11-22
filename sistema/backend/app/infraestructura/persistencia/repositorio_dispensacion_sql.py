"""Adaptador de RepositorioDispensacion (RI-17, CU-06)."""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.farmacia.dispensacion import (
    CATALOGO_GTIN,
    ProductoARegistrar,
    ProductoCatalogo,
    RepositorioDispensacion,
)
from app.infraestructura.persistencia.modelos_catalogo_gtin import (
    CatalogoGtinProductoModelo,
    CatalogoGtinVersionModelo,
)
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo


def a_producto_catalogo(fila: CatalogoGtinProductoModelo) -> ProductoCatalogo:
    return ProductoCatalogo(
        codigo=fila.codigo,
        tipo_producto_tedef=fila.tipo_producto_tedef,
        nombre=fila.nombre,
        denominacion_comun=fila.denominacion_comun,
        concentracion=fila.concentracion,
        forma_farmaceutica=fila.forma_farmaceutica,
        version_id=fila.version_id,
    )


class RepositorioDispensacionSql(RepositorioDispensacion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def _version_vigente(self) -> int | None:
        return await self._sesion.scalar(sa.select(sa.func.max(CatalogoGtinVersionModelo.id)))

    async def fecha_prestacion(self, cuenta_medica_id: int) -> date | None:
        fecha: date | None = await self._sesion.scalar(
            sa.select(CuentaMedicaModelo.fecha_prestacion).where(
                CuentaMedicaModelo.id == cuenta_medica_id
            )
        )
        return fecha

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None:
        version_id = await self._version_vigente()
        if version_id is None:
            return None
        fila = (
            await self._sesion.execute(
                sa.select(CatalogoGtinProductoModelo).where(
                    CatalogoGtinProductoModelo.version_id == version_id,
                    CatalogoGtinProductoModelo.codigo == codigo,
                )
            )
        ).scalar_one_or_none()
        return a_producto_catalogo(fila) if fila is not None else None

    async def buscar_catalogo(self, texto: str, limite: int) -> list[ProductoCatalogo]:
        version_id = await self._version_vigente()
        if version_id is None:
            return []
        consulta = sa.select(CatalogoGtinProductoModelo).where(
            CatalogoGtinProductoModelo.version_id == version_id
        )
        if texto:
            patron = f"%{texto}%"
            consulta = consulta.where(
                sa.or_(
                    CatalogoGtinProductoModelo.codigo.ilike(patron),
                    CatalogoGtinProductoModelo.nombre.ilike(patron),
                    CatalogoGtinProductoModelo.denominacion_comun.ilike(patron),
                )
            )
        filas = await self._sesion.execute(
            consulta.order_by(CatalogoGtinProductoModelo.nombre).limit(limite)
        )
        return [a_producto_catalogo(fila) for fila in filas.scalars().all()]

    async def existe_cie10(self, codigo: str) -> bool:
        version_id = await self._sesion.scalar(sa.select(sa.func.max(Cie10VersionModelo.id)))
        if version_id is None:
            return False
        encontrado = await self._sesion.scalar(
            sa.select(sa.literal(True)).where(
                Cie10CodigoModelo.cie10_version_id == version_id,
                Cie10CodigoModelo.codigo == codigo,
            )
        )
        return bool(encontrado)

    async def _renumerar(self, cuenta_medica_id: int) -> int:
        """Deja los productos de la cuenta numerados 1..n (T4 campo 6) y
        devuelve n. En orden ascendente cada fila baja a un numero libre,
        asi que la llave unica (cuenta, correlativo) no choca."""
        filas = (
            await self._sesion.execute(
                sa.select(ProductoFacturadoModelo.id, ProductoFacturadoModelo.correlativo)
                .where(ProductoFacturadoModelo.cuenta_medica_id == cuenta_medica_id)
                .order_by(ProductoFacturadoModelo.correlativo)
            )
        ).all()
        for nuevo, (producto_id, actual) in enumerate(filas, start=1):
            if actual != nuevo:
                await self._sesion.execute(
                    sa.update(ProductoFacturadoModelo)
                    .where(ProductoFacturadoModelo.id == producto_id)
                    .values(correlativo=nuevo)
                    .execution_options(synchronize_session="fetch")
                )
        return len(filas)

    async def guardar(self, producto: ProductoARegistrar) -> tuple[int, int]:
        # Tambien corrige los huecos que dejo la version anterior al quitar.
        correlativo = await self._renumerar(producto.cuenta_medica_id) + 1
        datos = producto.datos
        fila = ProductoFacturadoModelo(
            cuenta_medica_id=producto.cuenta_medica_id,
            correlativo=correlativo,
            tipo_producto=producto.catalogo.tipo_producto_tedef,
            catalogo=CATALOGO_GTIN,
            codigo_producto=producto.catalogo.codigo,
            catalogo_gtin_version_id=producto.catalogo.version_id,
            fecha_dispensacion=datos.fecha_dispensacion,
            cantidad_venta=datos.cantidad_venta,
            tipo_unidad_dispensacion=datos.tipo_unidad_dispensacion,
            monto_unitario_sin_impuesto=datos.monto_unitario,
            monto_presentado=producto.monto_presentado,
            monto_no_cubierto=datos.monto_no_cubierto,
            diagnostico_asociado_cie10=datos.diagnostico_asociado_cie10 or None,
            exento_igv=datos.exento_igv,
            guia_farmacia=datos.guia_farmacia or None,
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        return fila.id, correlativo

    async def quitar(self, cuenta_medica_id: int, producto_id: int) -> str | None:
        fila = await self._sesion.get(ProductoFacturadoModelo, producto_id)
        if fila is None or fila.cuenta_medica_id != cuenta_medica_id:
            return None
        codigo = fila.codigo_producto
        await self._sesion.delete(fila)
        await self._sesion.flush()
        await self._renumerar(cuenta_medica_id)
        return codigo
