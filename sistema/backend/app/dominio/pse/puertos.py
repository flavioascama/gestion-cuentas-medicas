"""Puertos de la emision del comprobante de pago (adenda de ingesta y
completitud): PSE (Proveedor de Servicios Electronicos), la pieza de
completitud que antes de esta adenda no tenia ninguna forma de
resolverse (ver el docstring anterior de ConsultarCompletitudCuenta en
casos_uso_ingesta.py, y docs/ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ErrorCuentaNoEncontrada(Exception):
    def __init__(self, cuenta_id: int) -> None:
        super().__init__(f"No existe la cuenta medica {cuenta_id}.")
        self.cuenta_id = cuenta_id


class ErrorComprobanteYaExiste(Exception):
    def __init__(self, cuenta_id: int) -> None:
        super().__init__(f"La cuenta {cuenta_id} ya tiene un comprobante de pago.")
        self.cuenta_id = cuenta_id


@dataclass(frozen=True, slots=True)
class ComprobantePse:
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date


@dataclass(frozen=True, slots=True)
class ResultadoEmisionComprobante:
    documento_id: int
    comprobante: ComprobantePse


class EmisorPse(Protocol):
    async def emitir(self, ruc_ipress: str, codigo_ipress: str) -> ComprobantePse: ...


class RepositorioComprobantePago(Protocol):
    async def obtener_ipress_propia(self) -> tuple[str, str]:
        """(ruc, codigo_ipress) de la clinica que opera el sistema."""
        ...

    async def guardar_comprobante(self, cuenta_id: int, comprobante: ComprobantePse) -> int:
        """Devuelve el id de la fila `documento_facturador` creada.

        Lanza ErrorCuentaNoEncontrada si `cuenta_id` no existe, o
        ErrorComprobanteYaExiste si la cuenta ya tiene uno (columna
        `cuenta_id` es UNIQUE, Seccion 6.1: un comprobante por cuenta)."""
        ...
