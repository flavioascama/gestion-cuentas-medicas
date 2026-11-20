"""Montos del lote y del comprobante: lo cubierto por cada procedimiento y
por cada producto de farmacia, los grupos de gasto de T2 (campos 35 a 48) y
lo facturado en T1 (campos 17 a 24). Separado de constructor_lote.py por el
limite de lineas por archivo (GUIA_ESTILO_CODIGO.md, Seccion 3).

Desde el 2026-11-18 los productos de farmacia suman al total facturado. El
criterio C3 del campo 40 de T2 pide la suma de la Tabla 4 (monto presentado
menos monto no cubierto) de los productos no exonerados de IGV, y el del
campo 42 la de los exonerados. Antes ambos iban en 0.00 aunque el lote
llevara la Tabla 4, y el comprobante no cobraba la farmacia.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.dominio.integracion.atencion_hospitalaria import AREA_IMAGENES, AREA_LABORATORIO
from app.dominio.integracion.esquema import CampoEsquema
from app.dominio.integracion.lote import (
    ContextoLote,
    DocumentoLote,
    ProcedimientoLote,
    ProductoLote,
)
from app.infraestructura.tedef.escritor_ancho_fijo import formatear_monto

CERO = Decimal("0.00")
DOS_DECIMALES = Decimal("0.01")
EXONERADO_IGV = "D"

# Tipos de Documento de Pago autorizados por la SUNAT via FUA/Codigo Unico
# (Seccion 7.9, T1 criterio C6 del campo 22 y 24): fuerzan monto 0.00.
_TIPOS_DOCUMENTO_SIN_MONTO = {"10", "11"}


def monto_presentado(procedimiento: ProcedimientoLote) -> Decimal:
    """T3 campo 19, formula literal de la descripcion del campo: cantidad
    multiplicada por monto unitario."""

    return (Decimal(procedimiento.cantidad) * procedimiento.monto_unitario).quantize(
        DOS_DECIMALES, rounding=ROUND_HALF_UP
    )


def monto_no_cubierto(procedimiento: ProcedimientoLote) -> Decimal:
    """T3 campo 20: lo que no cubre la IAFAS es lo que asume el paciente
    via copagos (docs/DECISIONES.md, correccion del 2026-09-16)."""

    return procedimiento.copago_variable + procedimiento.copago_fijo


def monto_cubierto(procedimiento: ProcedimientoLote) -> Decimal:
    return monto_presentado(procedimiento) - monto_no_cubierto(procedimiento)


def monto_presentado_producto(producto: ProductoLote) -> Decimal:
    """T4 campo 15: cantidad vendida por monto unitario sin impuesto."""

    return (producto.cantidad_venta * producto.monto_unitario).quantize(
        DOS_DECIMALES, rounding=ROUND_HALF_UP
    )


def monto_cubierto_producto(producto: ProductoLote) -> Decimal:
    return monto_presentado_producto(producto) - producto.monto_no_cubierto


@dataclass(frozen=True, slots=True)
class BasesFacturacion:
    """Lo que T1 toma de T2 para calcular lo facturado (criterios C4 y C6)."""

    total_cubierto: Decimal
    exonerado_igv: Decimal
    copagos_afectos: Decimal
    copagos_exonerados: Decimal


@dataclass(frozen=True, slots=True)
class GastosPrestacion:
    """Los grupos de gasto de una prestacion (T2, campos 35 a 48). Desde el
    2026-11-19 los procedimientos se reparten por su area entre los campos
    35, 38 y 39. Los que el prototipo no modela (36, 37, 41 y 43) y el
    copago fijo exonerado (45) son siempre 0.00 (docs/DECISIONES.md)."""

    procedimientos: Decimal  # campo 35
    farmacia: Decimal  # campo 40
    exonerado_igv: Decimal  # campo 42
    copago_fijo_afecto: Decimal  # campo 44
    copago_variable_afecto: Decimal  # campo 46
    copago_variable_exonerado: Decimal  # campo 47
    laboratorio: Decimal = CERO  # campo 38
    imagenes: Decimal = CERO  # campo 39

    @property
    def total_cubierto(self) -> Decimal:
        """Campo 48: suma de los campos 35 a 43."""
        return (
            self.procedimientos
            + self.laboratorio
            + self.imagenes
            + self.farmacia
            + self.exonerado_igv
        )

    @property
    def bases(self) -> BasesFacturacion:
        return BasesFacturacion(
            total_cubierto=self.total_cubierto,
            exonerado_igv=self.exonerado_igv,
            copagos_afectos=self.copago_fijo_afecto + self.copago_variable_afecto,
            copagos_exonerados=self.copago_variable_exonerado,
        )


def calcular_gastos(
    procedimientos: tuple[ProcedimientoLote, ...], productos: tuple[ProductoLote, ...]
) -> GastosPrestacion:
    """Los procedimientos van todos como no exonerados (T3 campo 22 fijo en
    'A'); cada producto de farmacia, segun su indicador (T4 campo 18)."""

    afectos = [p for p in productos if p.exento_igv != EXONERADO_IGV]
    exonerados = [p for p in productos if p.exento_igv == EXONERADO_IGV]

    def _cubierto_del_area(area: str) -> Decimal:
        return sum((monto_cubierto(p) for p in procedimientos if p.area == area), CERO)

    laboratorio = _cubierto_del_area(AREA_LABORATORIO)
    imagenes = _cubierto_del_area(AREA_IMAGENES)
    return GastosPrestacion(
        # Campo 35: todo lo que no es laboratorio ni imagenes (grupos 4 y 5).
        procedimientos=sum((monto_cubierto(p) for p in procedimientos), CERO)
        - laboratorio
        - imagenes,
        laboratorio=laboratorio,
        imagenes=imagenes,
        farmacia=sum((monto_cubierto_producto(p) for p in afectos), CERO),
        exonerado_igv=sum((monto_cubierto_producto(p) for p in exonerados), CERO),
        copago_fijo_afecto=sum((p.copago_fijo for p in procedimientos), CERO),
        copago_variable_afecto=sum((p.copago_variable for p in procedimientos), CERO)
        + sum((p.copago for p in afectos), CERO),
        copago_variable_exonerado=sum((p.copago for p in exonerados), CERO),
    )


def copago_del_asegurado(gastos: GastosPrestacion) -> Decimal:
    """Lo que el calculo atribuye al asegurado: los copagos de T2 (campos
    44, 46 y 47), sin cambiar el criterio con que se calculan."""
    return (
        gastos.copago_fijo_afecto + gastos.copago_variable_afecto + gastos.copago_variable_exonerado
    )


def campos_montos_t2(gastos: GastosPrestacion, campo: dict[int, CampoEsquema]) -> dict[int, str]:
    """Campos 35 a 48 de T2, ya con el formato del estandar."""

    valores = {numero: CERO for numero in range(35, 49)}
    valores[35] = gastos.procedimientos
    valores[38] = gastos.laboratorio
    valores[39] = gastos.imagenes
    valores[40] = gastos.farmacia
    valores[42] = gastos.exonerado_igv
    valores[44] = gastos.copago_fijo_afecto
    valores[46] = gastos.copago_variable_afecto
    valores[47] = gastos.copago_variable_exonerado
    valores[48] = gastos.total_cubierto
    return {numero: formatear_monto(valor, campo[numero]) for numero, valor in valores.items()}


@dataclass(frozen=True, slots=True)
class MontosFacturados:
    """Lo que se le factura a la IAFAS por una prestacion: base imponible,
    IGV y total (T1, campos 22 a 24)."""

    base_imponible: Decimal
    igv: Decimal
    total_facturado: Decimal

    @property
    def valor_venta(self) -> Decimal:
        """Lo facturado sin el IGV: la base imponible mas lo exonerado."""
        return self.total_facturado - self.igv


def _facturar(
    tipo_documento_pago: str, tasa_igv: Decimal, bases: BasesFacturacion
) -> MontosFacturados:
    """La regla de T1 (criterios C4 y C6) en un solo lugar: la usan el lote
    y el comprobante de pago."""
    sin_monto = tipo_documento_pago in _TIPOS_DOCUMENTO_SIN_MONTO
    base_imponible = bases.total_cubierto - bases.exonerado_igv - bases.copagos_afectos
    if base_imponible < 0 or sin_monto:
        base_imponible = CERO  # criterios C4 y C6
    igv = (base_imponible * tasa_igv).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
    total_facturado = base_imponible + igv + bases.exonerado_igv - bases.copagos_exonerados
    if sin_monto:
        return MontosFacturados(CERO, CERO, CERO)
    return MontosFacturados(base_imponible, igv, total_facturado)


def calcular_montos_facturados(
    tipo_documento_pago: str, gastos: GastosPrestacion, tasa_igv: Decimal
) -> MontosFacturados:
    """Los montos de T1 sin armar el lote: lo que el comprobante de pago
    guarda y muestra (2026-11-18)."""
    return _facturar(tipo_documento_pago, tasa_igv, gastos.bases)


@dataclass(frozen=True, slots=True)
class MontosT1:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): los
    montos de T1 (campos 17 a 24), todos derivados de los grupos de gasto
    ya calculados en T2."""

    exonerado_igv: Decimal
    copago_fijo_afecto: Decimal
    copago_fijo_exonerado: Decimal
    copago_variable_afecto: Decimal
    copago_variable_exonerado: Decimal
    base_imponible: Decimal
    igv: Decimal
    total_facturado: Decimal


def calcular_montos_t1(
    documento: DocumentoLote, contexto: ContextoLote, valores_t2: dict[int, str]
) -> MontosT1:
    def _monto_t2(numero: int) -> Decimal:
        return Decimal(valores_t2[numero].strip())

    copago_fijo_afecto = _monto_t2(44)
    copago_fijo_exonerado = _monto_t2(45)
    copago_variable_afecto = _monto_t2(46)
    copago_variable_exonerado = _monto_t2(47)
    facturado = _facturar(
        documento.tipo_documento_pago,
        contexto.tasa_igv,
        BasesFacturacion(
            total_cubierto=_monto_t2(48),
            exonerado_igv=_monto_t2(42),
            copagos_afectos=copago_fijo_afecto + copago_variable_afecto,
            copagos_exonerados=copago_fijo_exonerado + copago_variable_exonerado,
        ),
    )
    return MontosT1(
        exonerado_igv=_monto_t2(42),
        copago_fijo_afecto=copago_fijo_afecto,
        copago_fijo_exonerado=copago_fijo_exonerado,
        copago_variable_afecto=copago_variable_afecto,
        copago_variable_exonerado=copago_variable_exonerado,
        base_imponible=facturado.base_imponible,
        igv=facturado.igv,
        total_facturado=facturado.total_facturado,
    )
