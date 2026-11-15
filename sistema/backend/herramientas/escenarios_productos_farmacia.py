"""Asigna un producto de farmacia del catalogo GTIN transcrito a un
subconjunto de cuentas medicas sinteticas (Seccion 4, Fase 17), separado
de generar_datos_sinteticos.py para no superar el limite de 400 lineas
por archivo (GUIA_ESTILO_CODIGO.md, Seccion 3)."""

from __future__ import annotations

import random
from typing import Any

import yaml
from faker import Faker

from app.compartido.rutas import RAIZ_BACKEND

RUTA_CATALOGO_GTIN = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "catalogo_gtin.yaml"

# Letras del campo 7 presentes en configuracion/reglas_tedef/catalogo_gtin.yaml:
# un escenario de producto de farmacia por cada una, la ultima ademas como
# escenario de producto no cubierto (Seccion 4).
_LETRAS_PRODUCTO_DEMO = ("M", "I", "B", "A")


def _cargar_catalogo_gtin() -> list[dict[str, Any]]:
    with RUTA_CATALOGO_GTIN.open(encoding="utf-8") as archivo:
        catalogo: list[dict[str, Any]] = yaml.safe_load(archivo)
    return catalogo


def _seleccionar_productos_demo(catalogo: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un producto real del catalogo transcrito por cada letra de
    `_LETRAS_PRODUCTO_DEMO` (Regla 1: el codigo no se inventa, se toma tal
    cual de catalogo_gtin.yaml)."""

    return [
        next(producto for producto in catalogo if producto["tipo_producto_tedef"] == letra)
        for letra in _LETRAS_PRODUCTO_DEMO
    ]


def _producto_dispensado_demo(
    producto_catalogo: dict[str, Any], no_cubierto: bool, faker: Faker
) -> dict[str, Any]:
    cantidad = random.randint(1, 3)
    monto_unitario = round(random.uniform(10, 200), 2)
    return {
        "codigo_producto": producto_catalogo["codigo"],
        "tipo_producto": producto_catalogo["tipo_producto_tedef"],
        "catalogo": "1",  # GTIN (Seccion 16, supuesto 5: unico catalogo transcrito)
        "cantidad_venta": cantidad,
        "tipo_unidad_dispensacion": faker.random_element(["1", "2"]),
        "monto_unitario": monto_unitario,
        # Escenario "producto no cubierto" (Seccion 4): el IAFAS no cubre
        # una fraccion del monto presentado.
        "monto_no_cubierto": round(cantidad * monto_unitario * 0.3, 2) if no_cubierto else 0.0,
    }


def asignar_productos_demo(lotes: dict[str, list[dict[str, Any]]], faker: Faker) -> None:
    """Muta `lotes` in place: agrega `productos` a las primeras
    `len(_LETRAS_PRODUCTO_DEMO)` cuentas generadas (sin importar a que
    lote pertenezcan)."""

    productos_demo = _seleccionar_productos_demo(_cargar_catalogo_gtin())
    todas_las_cuentas = [cuenta for cuentas in lotes.values() for cuenta in cuentas]
    for cuenta, producto_catalogo in zip(todas_las_cuentas, productos_demo, strict=False):
        no_cubierto = producto_catalogo is productos_demo[-1]
        cuenta["productos"] = [_producto_dispensado_demo(producto_catalogo, no_cubierto, faker)]
