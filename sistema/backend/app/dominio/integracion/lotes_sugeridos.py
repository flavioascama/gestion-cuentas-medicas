"""Lotes sugeridos para "Generar lote" (pedido del usuario, 2026-11-17).

El sistema ya conoce de cada cuenta facturada su IAFAS y el mes de su
comprobante de pago, asi que arma los grupos en lugar de pedirle al
analista que elija la IAFAS y escriba el periodo. Un lote va a una sola
IAFAS (su codigo va en el nombre del archivo y la numeracion es por
IAFAS) y lleva un solo periodo: el mes de emision de sus comprobantes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class ErrorPeriodoLote(Exception):
    """Las cuentas elegidas no definen un unico periodo de facturacion."""


def periodo_de_comprobante(fecha_emision: date) -> str:
    return f"{fecha_emision.year:04d}{fecha_emision.month:02d}"


def periodo_unico(fechas_emision: Iterable[date]) -> str:
    """El periodo de un lote: el mes de emision de sus comprobantes."""
    periodos = sorted({periodo_de_comprobante(fecha) for fecha in fechas_emision})
    if not periodos:
        raise ErrorPeriodoLote("Ninguna de las cuentas elegidas esta facturada.")
    if len(periodos) > 1:
        raise ErrorPeriodoLote(
            "Las cuentas elegidas tienen comprobantes de mas de un mes "
            f"({', '.join(periodos)}); cada lote lleva un solo periodo."
        )
    return periodos[0]


@dataclass(frozen=True, slots=True)
class CuentaPorLotear:
    cuenta_id: int
    identificacion_interna: str
    nombres_asegurado: str
    apellidos_asegurado: str
    iafas_id: int
    iafas_codigo: str
    iafas_razon_social: str
    fecha_emision: date
    monto: Decimal
    # Lo que le falta para entrar a un lote, en palabras simples; vacio si
    # esta lista (dominio/integracion/pendientes_lote.py).
    pendientes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LoteSugerido:
    iafas_id: int
    iafas_codigo: str
    iafas_razon_social: str
    periodo: str
    cuentas: tuple[CuentaPorLotear, ...]
    # Cuentas del mismo grupo que todavia no pueden entrar (2026-11-18).
    con_pendientes: tuple[CuentaPorLotear, ...] = ()

    @property
    def monto_total(self) -> Decimal:
        return sum((cuenta.monto for cuenta in self.cuentas), Decimal("0.00"))


class RepositorioCuentasPorLotear(Protocol):
    async def cuentas_por_lotear(self) -> list[CuentaPorLotear]:
        """Cuentas FACTURADA que no estan en un lote en curso (generado,
        cargado o validado, todavia sin remitir) y vigente."""
        ...


def agrupar_en_lotes_sugeridos(cuentas: Iterable[CuentaPorLotear]) -> list[LoteSugerido]:
    """Un grupo por IAFAS y periodo; primero el periodo mas antiguo."""
    grupos: dict[tuple[str, str], list[CuentaPorLotear]] = {}
    for cuenta in cuentas:
        clave = (periodo_de_comprobante(cuenta.fecha_emision), cuenta.iafas_codigo)
        grupos.setdefault(clave, []).append(cuenta)
    sugeridos: list[LoteSugerido] = []
    for (periodo, _codigo), miembros in sorted(grupos.items()):
        primera = miembros[0]
        ordenadas = sorted(miembros, key=lambda c: c.identificacion_interna)
        sugeridos.append(
            LoteSugerido(
                iafas_id=primera.iafas_id,
                iafas_codigo=primera.iafas_codigo,
                iafas_razon_social=primera.iafas_razon_social,
                periodo=periodo,
                cuentas=tuple(c for c in ordenadas if not c.pendientes),
                con_pendientes=tuple(c for c in ordenadas if c.pendientes),
            )
        )
    return sugeridos


class SugerirLotes:
    def __init__(self, repositorio: RepositorioCuentasPorLotear) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[LoteSugerido]:
        return agrupar_en_lotes_sugeridos(await self._repositorio.cuentas_por_lotear())
