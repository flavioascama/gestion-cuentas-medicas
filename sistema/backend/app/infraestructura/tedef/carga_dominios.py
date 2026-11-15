"""Carga configuracion/reglas_tedef/dominios.yaml (Seccion 7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.compartido.rutas import RAIZ_BACKEND

RUTA_DOMINIOS = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "dominios.yaml"


@dataclass(frozen=True, slots=True)
class Dominio:
    codigos_validos: frozenset[str]
    confirmado: bool


@lru_cache
def cargar_dominios(ruta: Path = RUTA_DOMINIOS) -> dict[tuple[str, int], Dominio]:
    """{(tabla, campo_numero): Dominio}."""

    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or []
    return {
        (d["tabla"], d["campo"]): Dominio(
            codigos_validos=frozenset(v["codigo"] for v in d["valores"]),
            confirmado=d["confirmado"],
        )
        for d in datos
    }
