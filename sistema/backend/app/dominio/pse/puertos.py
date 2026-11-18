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


class ErrorFaltaParaFacturar(Exception):
    """El comprobante se emite al final: con el asegurado acreditado, el
    diagnostico registrado y lo que se va a facturar ya codificado."""

    def __init__(self, faltantes: tuple[str, ...]) -> None:
        super().__init__("Antes de emitir el comprobante falta: " + ", ".join(faltantes) + ".")
        self.faltantes = faltantes


@dataclass(frozen=True, slots=True)
class RequisitosComprobante:
    """Lo que una cuenta debe tener antes de facturarse (2026-11-18): un
    comprobante sin procedimientos no factura nada, y sin acreditacion no
    se conocen los copagos."""

    acreditada: bool
    con_diagnostico: bool
    procedimientos: int

    def faltantes(self) -> tuple[str, ...]:
        faltantes = []
        if not self.acreditada:
            faltantes.append("la acreditación del asegurado")
        if not self.con_diagnostico:
            faltantes.append("el diagnóstico principal")
        if self.procedimientos == 0:
            faltantes.append("al menos un procedimiento")
        return tuple(faltantes)


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


@dataclass(frozen=True, slots=True)
class NotaPse:
    """La identificacion que el PSE le da a una nota de credito o debito."""

    serie: str
    numero: str
    fecha_emision: date


class EmisorPse(Protocol):
    async def emitir(self, ruc_ipress: str, codigo_ipress: str) -> ComprobantePse: ...

    async def emitir_nota(self, ruc_ipress: str, codigo_ipress: str, tipo: str) -> NotaPse:
        """`tipo`: C (credito) o D (debito)."""
        ...


class RepositorioComprobantePago(Protocol):
    async def obtener_ipress_propia(self) -> tuple[str, str]:
        """(ruc, codigo_ipress) de la clinica que opera el sistema."""
        ...

    async def requisitos_para_facturar(self, cuenta_id: int) -> RequisitosComprobante | None:
        """None si la cuenta no existe."""
        ...

    async def guardar_comprobante(self, cuenta_id: int, comprobante: ComprobantePse) -> int:
        """Devuelve el id de la fila `documento_facturador` creada.

        Lanza ErrorCuentaNoEncontrada si `cuenta_id` no existe, o
        ErrorComprobanteYaExiste si la cuenta ya tiene uno (columna
        `cuenta_id` es UNIQUE, Seccion 6.1: un comprobante por cuenta)."""
        ...
