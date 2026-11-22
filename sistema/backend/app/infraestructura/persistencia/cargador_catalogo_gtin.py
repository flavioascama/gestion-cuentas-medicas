"""Carga del catalogo GTIN versionado (Seccion 10, Fase 17), compartida por
`herramientas/cargar_catalogo_gtin.py` y por la pantalla de administracion
(CU-18, 2026-11-13): lee configuracion/reglas_tedef/catalogo_gtin.yaml y
crea una version nueva con sus productos, sin tocar las anteriores.

La trazabilidad de cada producto a su captura y fila de origen (Seccion
3.3) vive aqui, no en el archivo de configuracion."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.rutas import RAIZ_BACKEND
from app.dominio.farmacia.puertos import CargadorCatalogoGtin, VersionCatalogoGtin
from app.infraestructura.persistencia.modelos_catalogo_gtin import (
    CatalogoGtinProductoModelo,
    CatalogoGtinVersionModelo,
)

RUTA_CATALOGO_GTIN = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "catalogo_gtin.yaml"

TRAZABILIDAD_CATALOGO_GTIN: dict[str, tuple[str, int]] = {
    "008400001344": ("gtin_01.png", 3),  # GODEK / KETOROLACO
    "030006030039": ("gtin_01.png", 7),  # SINGULAIR / MONTELUKAST
    "030900130507": ("gtin_01.png", 11),  # SOLU-CORTEF / HIDROCORTISONA
    "0380652555906": ("gtin_01.png", 13),  # ACRYSOF SINGLE-PIECE
    "041167627624": ("gtin_01.png", 18),  # SELSUN AMARILLO
    "044677100403": ("gtin_01.png", 20),  # LANOLINA HPA LANSINOH
    "070074114323": ("gtin_01.png", 24),  # ENSURE ADVANCE VAINILLA
    "070074124940": ("gtin_01.png", 30),  # GLUCERNA NF VAINILLA
    "0707387792114": ("gtin_01.png", 32),  # CAVILON NO STING BARRIER FILM
    "0736372872630": ("gtin_01.png", 35),  # HIDROCIL PENSOLAC
    "0745853642440": ("gtin_01.png", 40),  # TEGLINIL / SILODOSINA
    "0745853837341": ("gtin_01.png", 41),  # FORTEBON D3
    "30106659": ("gtin_02.png", 12),  # CICAPLAST LEVRES
    "3029939171688": ("gtin_02.png", 16),  # CETAPHIL PIEL SENSIBLE
    "3031500311423": ("gtin_02.png", 17),  # TEEN DERM
    "311845319913": ("gtin_02.png", 22),  # VITAMIN C / ACIDO ASCORBICO
    "311845320018": ("gtin_02.png", 23),  # VITAMIN B-12 / CIANOCOBALAMINA
    "311845322210": ("gtin_02.png", 30),  # FOLIC ACID / ACIDO FOLICO
    "311845379313": ("gtin_02.png", 36),  # ZINC
}


class ErrorCatalogoGtinSinTrazabilidad(Exception):
    pass


def leer_productos_catalogo_gtin(ruta: Path = RUTA_CATALOGO_GTIN) -> list[dict[str, object]]:
    with ruta.open(encoding="utf-8") as archivo:
        productos: list[dict[str, object]] = yaml.safe_load(archivo)
    faltantes = [p["codigo"] for p in productos if p["codigo"] not in TRAZABILIDAD_CATALOGO_GTIN]
    if faltantes:
        raise ErrorCatalogoGtinSinTrazabilidad(
            f"Sin trazabilidad (captura/fila) registrada para: {faltantes}. "
            "Agregar una entrada en TRAZABILIDAD_CATALOGO_GTIN antes de cargar."
        )
    return productos


async def insertar_version_catalogo_gtin(
    sesion: AsyncSession,
    productos: list[dict[str, object]],
    trazabilidad: Mapping[str, tuple[str, int]] = TRAZABILIDAD_CATALOGO_GTIN,
    ruta_origen: str = str(RUTA_CATALOGO_GTIN),
) -> VersionCatalogoGtin:
    """Agrega la version y sus productos a la sesion (sin confirmar)."""
    version = CatalogoGtinVersionModelo(ruta_origen=ruta_origen)
    sesion.add(version)
    await sesion.flush()
    for producto in productos:
        captura, fila = trazabilidad[str(producto["codigo"])]
        sesion.add(
            CatalogoGtinProductoModelo(
                version_id=version.id,
                codigo=producto["codigo"],
                tipo_codigo=producto["tipo_codigo"],
                tipo_producto_catalogo=producto["tipo_producto_catalogo"],
                tipo_producto_tedef=producto["tipo_producto_tedef"],
                nombre=producto["nombre"],
                denominacion_comun=producto["denominacion_comun"],
                concentracion=producto.get("concentracion"),
                forma_farmaceutica=producto.get("forma_farmaceutica"),
                captura=captura,
                fila=fila,
            )
        )
    await sesion.flush()
    await sesion.refresh(version)
    return VersionCatalogoGtin(
        id=version.id,
        ruta_origen=version.ruta_origen,
        conteo=len(productos),
        cargado_en=version.cargado_en,
    )


class CargadorCatalogoGtinSql(CargadorCatalogoGtin):
    def __init__(
        self,
        sesion: AsyncSession,
        productos: list[dict[str, object]],
        trazabilidad: Mapping[str, tuple[str, int]],
        nombre_archivo: str,
    ) -> None:
        self._sesion = sesion
        self._productos = productos
        self._trazabilidad = trazabilidad
        self._nombre_archivo = nombre_archivo

    async def cargar(self) -> VersionCatalogoGtin:
        return await insertar_version_catalogo_gtin(
            self._sesion, self._productos, self._trazabilidad, self._nombre_archivo
        )
