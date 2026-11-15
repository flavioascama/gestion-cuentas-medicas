"""Representacion tipada de una fila de configuracion/reglas_tedef/criterios.csv
(Seccion 7.4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CriterioRegla:
    tabla: str
    campo_numero: int
    campo_nombre: str
    criterio_id: str
    texto_literal: str
    implementada: bool
    regla: str
