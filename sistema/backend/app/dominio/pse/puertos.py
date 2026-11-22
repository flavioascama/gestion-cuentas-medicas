"""Puertos de la emision del comprobante de pago (adenda de ingesta y
completitud): PSE (Proveedor de Servicios Electronicos), la pieza de
completitud que antes de esta adenda no tenia ninguna forma de
resolverse (ver el docstring anterior de ConsultarCompletitudCuenta en
casos_uso_ingesta.py, y docs/ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

# El sistema solo emite facturas a la aseguradora (catalogo SUNAT 01).
TIPO_FACTURA = "01"


class ErrorCuentaNoEncontrada(Exception):
    def __init__(self, cuenta_id: int) -> None:
        super().__init__("No existe la cuenta.")
        self.cuenta_id = cuenta_id


class ErrorComprobanteYaExiste(Exception):
    def __init__(self, cuenta_id: int) -> None:
        super().__init__("La cuenta ya tiene un comprobante de pago.")
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
    # Existe la acreditacion pero la aseguradora no cubre al asegurado.
    acreditable: bool = True
    # Atencion importada (2026-11-19): procedimientos aun sin codigo, y una
    # hospitalizacion sin carta de garantia registrada.
    por_codificar: int = 0
    falta_carta_garantia: bool = False
    # Control C-18: la acreditacion vigente se registro en contingencia y el
    # jefe la reviso no conforme.
    cobertura_no_conforme: bool = False

    def faltantes(self) -> tuple[str, ...]:
        faltantes = []
        if not self.acreditada:
            faltantes.append("la acreditación del asegurado")
        elif self.cobertura_no_conforme:
            faltantes.append("una verificación de cobertura conforme")
        elif not self.acreditable:
            faltantes.append("que la IAFAS acredite al asegurado")
        if not self.con_diagnostico:
            faltantes.append("el diagnóstico principal")
        if self.procedimientos == 0:
            faltantes.append("al menos un procedimiento")
        if self.por_codificar:
            faltantes.append("que se codifiquen todos los procedimientos de la atención")
        if self.falta_carta_garantia:
            faltantes.append("la carta de garantía de la hospitalización")
        return tuple(faltantes)


@dataclass(frozen=True, slots=True)
class ComprobantePse:
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date


@dataclass(frozen=True, slots=True)
class MontosComprobante:
    """Lo que factura un comprobante, con la regla de T1."""

    valor_venta: Decimal
    igv: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class CotejoMontos:
    """Los montos guardados en el comprobante frente a los que hoy factura
    la cuenta."""

    guardados: MontosComprobante | None
    actuales: MontosComprobante | None

    @property
    def desfasado(self) -> bool:
        # Los comprobantes anteriores al 2026-11-18 no guardaron montos: no
        # hay con que compararlos y no se consideran desfasados.
        if self.guardados is None or self.actuales is None:
            return False
        return self.guardados != self.actuales


@dataclass(frozen=True, slots=True)
class ClienteComprobante:
    """La aseguradora (IAFAS) a la que se le factura."""

    codigo_iafas: str
    razon_social: str


@dataclass(frozen=True, slots=True)
class DatosFacturacion:
    cliente: ClienteComprobante
    montos: MontosComprobante


@dataclass(frozen=True, slots=True)
class SolicitudComprobante:
    """Lo que se envia al PSE para emitir un comprobante: los montos se
    calculan antes, para que el PSE y el comprobante guardado digan lo
    mismo."""

    ruc_ipress: str
    codigo_ipress: str
    tipo_comprobante: str
    cliente: ClienteComprobante
    montos: MontosComprobante


@dataclass(frozen=True, slots=True)
class ComprobanteEmitido:
    """El comprobante que dio el PSE con los montos que se le enviaron; se
    guarda tal cual."""

    comprobante: ComprobantePse
    montos: MontosComprobante


@dataclass(frozen=True, slots=True)
class SolicitudNota:
    """Lo que se envia al PSE para emitir una nota: su monto y el
    comprobante al que se refiere."""

    ruc_ipress: str
    codigo_ipress: str
    tipo: str
    monto: Decimal
    referido: ComprobantePse


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
    async def emitir(self, solicitud: SolicitudComprobante) -> ComprobantePse: ...

    async def emitir_nota(self, solicitud: SolicitudNota) -> NotaPse:
        """`solicitud.tipo`: C (credito) o D (debito)."""
        ...


class RepositorioComprobantePago(Protocol):
    async def obtener_ipress_propia(self) -> tuple[str, str]:
        """(ruc, codigo_ipress) de la clinica que opera el sistema."""
        ...

    async def requisitos_para_facturar(self, cuenta_id: int) -> RequisitosComprobante | None:
        """None si la cuenta no existe."""
        ...

    async def datos_para_facturar(
        self, cuenta_id: int, tipo_comprobante: str
    ) -> DatosFacturacion | None:
        """La IAFAS de la cuenta y los montos con la regla de T1. None si la
        cuenta no existe o no tiene acreditacion (de ella salen los copagos)."""
        ...

    async def guardar_comprobante(self, cuenta_id: int, emitido: ComprobanteEmitido) -> int:
        """Devuelve el id de la fila `documento_facturador` creada.

        Lanza ErrorCuentaNoEncontrada si `cuenta_id` no existe, o
        ErrorComprobanteYaExiste si la cuenta ya tiene uno (columna
        `cuenta_id` es UNIQUE, Seccion 6.1: un comprobante por cuenta)."""
        ...


class RepositorioCotejoComprobante(Protocol):
    async def cotejar(self, cuenta_medica_id: int) -> CotejoMontos:
        """Montos guardados del comprobante y los que hoy calcula la cuenta."""
        ...
