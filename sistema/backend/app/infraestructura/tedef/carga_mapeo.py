"""Carga y verifica configuracion/mapeo/mapeo_tedef.yaml (Seccion 7.2).

Falla al cargar si falta una entrada para algun campo de T1, T2 o T3:
"El generador falla al arrancar si existe un campo de T1, T2 o T3 sin
entrada en el diccionario. Esto impide olvidos silenciosos." (Seccion 7.2)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.compartido.rutas import RAIZ_BACKEND
from app.infraestructura.tedef.carga_esquema import cargar_esquema

RUTA_MAPEO = RAIZ_BACKEND / "configuracion" / "mapeo" / "mapeo_tedef.yaml"

# Unicas tablas que este prototipo genera (Seccion 1.2); son las que el
# diccionario de mapeo debe cubrir por completo.
TABLAS_CON_MAPEO = ("T1", "T2", "T3")


@dataclass(frozen=True, slots=True)
class EntradaMapeo:
    tabla: str
    campo: int
    nombre: str
    origen: str
    expresion: str
    transformacion: str
    nota: str


class ErrorMapeoIncompleto(Exception):
    """Falta una entrada de T1, T2 o T3 en el diccionario de mapeo."""


def _construir_entrada(datos: dict[str, object]) -> EntradaMapeo:
    return EntradaMapeo(
        tabla=str(datos["tabla"]),
        campo=int(datos["campo"]),  # type: ignore[call-overload]
        nombre=str(datos["nombre"]),
        origen=str(datos["origen"]),
        expresion=str(datos["expresion"]),
        transformacion=str(datos.get("transformacion", "")),
        nota=str(datos.get("nota", "")),
    )


def _verificar_cobertura_completa(mapeo: dict[tuple[str, int], EntradaMapeo]) -> None:
    esquema = cargar_esquema()
    faltantes = [
        f"{tabla_id} campo {campo.numero} ({campo.nombre})"
        for tabla_id in TABLAS_CON_MAPEO
        for campo in esquema[tabla_id].campos
        if (tabla_id, campo.numero) not in mapeo
    ]
    if faltantes:
        raise ErrorMapeoIncompleto(
            "Faltan entradas en el diccionario de mapeo para: " + "; ".join(faltantes)
        )

    origenes_validos = {"columna", "constante", "calculado", "blanco"}
    invalidos = [
        f"{clave[0]} campo {clave[1]}: origen {entrada.origen!r} no reconocido"
        for clave, entrada in mapeo.items()
        if entrada.origen not in origenes_validos
    ]
    if invalidos:
        raise ErrorMapeoIncompleto("; ".join(invalidos))


@lru_cache
def version_mapeo(ruta: Path = RUTA_MAPEO) -> str:
    """RT-06: el diccionario de mapeo no declara un numero de version; su
    huella SHA-256 identifica sin ambiguedad el contenido con el que se
    genero cada lote (cualquier cambio de una entrada cambia la huella)."""

    return hashlib.sha256(ruta.read_bytes()).hexdigest()


@lru_cache
def cargar_mapeo(ruta: Path = RUTA_MAPEO) -> dict[tuple[str, int], EntradaMapeo]:
    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)

    mapeo = {(e["tabla"], e["campo"]): _construir_entrada(e) for e in datos}
    _verificar_cobertura_completa(mapeo)
    return mapeo
