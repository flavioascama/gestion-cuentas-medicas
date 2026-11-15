"""DTOs de dominio para construir un lote (Seccion 7.6): datos ya leidos
de los repositorios, sin SQLAlchemy. `GenerarLote` los ensambla; el
constructor de infraestructura los proyecta sobre T1, T2 y T3.

Simplificacion de esta fase, documentada en docs/DECISIONES.md: cada
documento facturador de este prototipo corresponde a exactamente una
cuenta medica, es decir una sola prestacion (T2) por documento. T1 campo
11 ("Cantidad de prestaciones") vale siempre 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProcedimientoLote:
    correlativo: int
    codigo_cpms: str
    descripcion: str
    fecha: date
    cantidad: int
    monto_unitario: Decimal
    copago_variable: Decimal
    copago_fijo: Decimal


@dataclass(frozen=True, slots=True)
class ProductoLote:
    """T4 (Seccion 10, Fase 17): un producto de farmacia dispensado.
    `catalogo` y `tipo_producto` ya vienen resueltos desde
    `producto_facturado` (Seccion 8.1: campos 7 a 9 del mapeo) -- el
    constructor de T4 no necesita consultar el catalogo GTIN de nuevo."""

    correlativo: int
    tipo_producto: str
    catalogo: str
    codigo_producto: str
    fecha_dispensacion: date
    cantidad_venta: Decimal
    tipo_unidad_dispensacion: str
    monto_unitario: Decimal
    copago: Decimal
    monto_no_cubierto: Decimal
    diagnostico_asociado_cie10: str | None
    exento_igv: str
    guia_farmacia: str | None
    cantidad_prescrita: Decimal | None


@dataclass(frozen=True, slots=True)
class PrestacionLote:
    codigo_prestacion_interno: str
    numero_historia_clinica: str
    tipo_documento_paciente: str
    numero_documento_paciente: str
    codigo_asegurado: str
    tipo_afiliacion: str
    codigo_autorizacion: str
    tipo_documento_autorizacion: str
    fecha_prestacion: date
    hora_prestacion: time
    # Catalogo oficial CIE-10 del MINSA cargado desde la Fase 17 (ver
    # herramientas/cargar_cie10.py); el validador de campo todavia no
    # comprueba este valor contra ese catalogo (Seccion 7.7, criterio C1
    # de T2 campo 18, no implementado).
    diagnostico_principal_cie10: str | None
    procedimientos: tuple[ProcedimientoLote, ...]
    # Seccion 8.1 (Fase 17): vacio para la mayoria de prestaciones -- T4
    # solo se genera "para las prestaciones que tengan productos
    # registrados" (Anexo 3).
    productos: tuple[ProductoLote, ...] = ()


@dataclass(frozen=True, slots=True)
class NotaLote:
    """T1 campos 25 a 29 (RI-11): la nota de credito o debito del
    comprobante, si tiene una."""

    tipo: str
    serie: str
    numero: str
    monto: Decimal
    fecha: date
    motivo: str


@dataclass(frozen=True, slots=True)
class DocumentoLote:
    documento_id: int
    cuenta_medica_id: int
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date
    fecha_primer_envio: date | None
    prestacion: PrestacionLote
    nota: NotaLote | None = None


@dataclass(frozen=True, slots=True)
class ContextoLote:
    numero_lote: str
    periodo: str
    generado_en: datetime
    ruc_ipress: str
    codigo_ipress: str
    codigo_iafas: str
    tasa_igv: Decimal
