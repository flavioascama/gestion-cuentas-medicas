"""Utilidad compartida de `app/api/`: extrae los campos de un objeto de
valor del dominio (`@dataclass(frozen=True, slots=True)`,
GUIA_ESTILO_CODIGO.md Seccion 2.2) como dict, para construir el esquema
Pydantic correspondiente con `Respuesta(**campos(valor))`.

`slots=True` no deja `__dict__` (bug real de la Fase 18: `Respuesta(**valor.__dict__)`
fallaba con `AttributeError` en cuanto `valor` traia datos reales -- las
pruebas con SQLite en memoria no lo notaron porque siempre pasaban listas
vacias por esa ruta). `dataclasses.fields()` funciona con o sin
`__slots__`, a diferencia de `__dict__`."""

from __future__ import annotations

import dataclasses
from typing import Any


def campos(valor: Any) -> dict[str, Any]:
    return {campo.name: getattr(valor, campo.name) for campo in dataclasses.fields(valor)}
