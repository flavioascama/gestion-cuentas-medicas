"""Pruebas del cargador del catalogo GTIN (Seccion 10, Fase 17): lectura
del catalogo real transcrito y carga en base de datos con trazabilidad."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_catalogo_gtin import (
    CatalogoGtinProductoModelo,
    CatalogoGtinVersionModelo,
)
from herramientas.cargar_catalogo_gtin import _cargar, _leer_productos


def prueba_leer_productos_devuelve_19_filas_con_trazabilidad() -> None:
    productos = _leer_productos()

    assert len(productos) == 19
    codigos = {p["codigo"] for p in productos}
    assert len(codigos) == 19  # ningun duplicado
    assert all(isinstance(p["codigo"], str) for p in productos)  # ceros a la izquierda intactos


def prueba_leer_productos_cubre_las_4_letras_del_campo_7() -> None:
    productos = _leer_productos()
    letras = {p["tipo_producto_tedef"] for p in productos}
    assert letras == {"M", "I", "B", "A"}


async def prueba_cargar_crea_version_con_19_productos_y_trazabilidad(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    productos = _leer_productos()

    version_id = await _cargar(productos, fabrica_sesiones)

    async with fabrica_sesiones() as sesion:
        version = await sesion.get(CatalogoGtinVersionModelo, version_id)
        assert version is not None

        total = await sesion.scalar(
            sa.select(sa.func.count())
            .select_from(CatalogoGtinProductoModelo)
            .where(CatalogoGtinProductoModelo.version_id == version_id)
        )
        assert total == 19

        # Codigo GTIN con ceros a la izquierda: sobrevive el viaje por
        # YAML y Postgres sin perderlos (Seccion 3.3).
        fila = await sesion.scalar(
            sa.select(CatalogoGtinProductoModelo).where(
                CatalogoGtinProductoModelo.version_id == version_id,
                CatalogoGtinProductoModelo.codigo == "008400001344",
            )
        )
        assert fila is not None
        assert fila.captura and fila.fila > 0
