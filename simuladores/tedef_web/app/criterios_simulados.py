"""Carga configuracion/criterios_simulados.yaml (Seccion 9.2: "un
subconjunto configurable de criterios adicionales"). Deliberadamente
pequeno: cada entrada cita el texto del Anexo 1 del que se tomo, para no
inventar un dominio que el Anexo 1 no confirma (Regla 1)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_RUTA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent / "configuracion" / "criterios_simulados.yaml"
)


@dataclass(frozen=True, slots=True)
class DominioSimulado:
    tabla: str
    campo: int
    nombre: str
    valores: frozenset[str]


@lru_cache
def cargar_dominios_simulados(ruta: Path = _RUTA_POR_DEFECTO) -> tuple[DominioSimulado, ...]:
    contenido = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return tuple(
        DominioSimulado(
            tabla=entrada["tabla"],
            campo=entrada["campo"],
            nombre=entrada["nombre"],
            valores=frozenset(entrada["valores"]),
        )
        for entrada in contenido["dominios"]
    )
