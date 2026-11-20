"""Procedimientos por codificar (2026-11-19): lo que trae la atencion
importada del sistema hospitalario es una descripcion con cantidad, monto,
fecha y area, sin codigo CPMS. Quedan pendientes hasta que el auditor los
confirma con un codigo del catalogo vigente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class ErrorProcedimientoPorCodificarInexistente(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ProcedimientoPorCodificar:
    id: int
    descripcion: str
    area: str
    cantidad: int
    monto_unitario: Decimal
    fecha: date


class RepositorioProcedimientosPorCodificar(Protocol):
    async def listar_pendientes(self, cuenta_medica_id: int) -> list[ProcedimientoPorCodificar]:
        """Los que aun no tienen procedimiento confirmado, en orden de llegada."""
        ...


class ListarProcedimientosPorCodificar:
    def __init__(self, repositorio: RepositorioProcedimientosPorCodificar) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> list[ProcedimientoPorCodificar]:
        return await self._repositorio.listar_pendientes(cuenta_medica_id)
