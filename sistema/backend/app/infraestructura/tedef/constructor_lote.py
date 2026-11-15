"""Constructor del lote (Seccion 7.2, 7.6): ejecuta el diccionario de
mapeo de `configuracion/mapeo/mapeo_tedef.yaml` con datos reales,
produciendo el texto de cada campo de T1, T2 y T3 para un documento
facturador. No escribe archivos: eso es tarea de GenerarLote, usando
`escritor_ancho_fijo.escribir_registro` con el resultado de estas
funciones.

Simplificacion de esta fase (docs/DECISIONES.md): cada documento
facturador tiene exactamente una prestacion (T2), asi que las sumas
"Tabla T2 ∑ ..." del Anexo 1 se reducen a leer esa unica fila. El RUC y el
codigo IPRESS son siempre los de la clinica que opera el sistema
(`ContextoLote`, origen=constante en el diccionario de mapeo): este
prototipo no modela derivaciones reales entre distintas IPRESS (ver
docs/PENDIENTES.md), por lo que "RUC de Entidad de Referencia" (T2 campo
27) siempre coincide con el propio.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.dominio.integracion.esquema import CampoEsquema, TablaEsquema
from app.dominio.integracion.lote import (
    ContextoLote,
    DocumentoLote,
    NotaLote,
    ProcedimientoLote,
    ProductoLote,
)
from app.infraestructura.tedef.escritor_ancho_fijo import (
    formatear_alfanumerico,
    formatear_fecha,
    formatear_hora,
    formatear_monto,
    formatear_numerico_con_ceros,
)

_CERO = Decimal("0.00")
_DOS_DECIMALES = Decimal("0.01")

# Tipos de Documento de Pago autorizados por la SUNAT via FUA/Codigo Unico
# (Seccion 7.9, T1 criterio C6 del campo 22 y 24): fuerzan monto 0.00.
_TIPOS_DOCUMENTO_SIN_MONTO = {"10", "11"}


def _monto_presentado(procedimiento: ProcedimientoLote) -> Decimal:
    """T3 campo 19, formula literal de la descripcion del campo: cantidad
    multiplicada por monto unitario."""

    return (Decimal(procedimiento.cantidad) * procedimiento.monto_unitario).quantize(
        _DOS_DECIMALES, rounding=ROUND_HALF_UP
    )


def _monto_no_cubierto(procedimiento: ProcedimientoLote) -> Decimal:
    """T3 campo 20: lo que no cubre la IAFAS es lo que asume el paciente
    via copagos (docs/DECISIONES.md, correccion del 2026-09-16)."""

    return procedimiento.copago_variable + procedimiento.copago_fijo


def _monto_cubierto(procedimiento: ProcedimientoLote) -> Decimal:
    return _monto_presentado(procedimiento) - _monto_no_cubierto(procedimiento)


def construir_t3(
    tabla: TablaEsquema,
    contexto: ContextoLote,
    documento: DocumentoLote,
    procedimiento: ProcedimientoLote,
) -> dict[int, str]:
    campo = {c.numero: c for c in tabla.campos}
    monto_presentado = _monto_presentado(procedimiento)
    monto_no_cubierto = _monto_no_cubierto(procedimiento)

    return {
        1: formatear_numerico_con_ceros(contexto.ruc_ipress, campo[1]),
        2: formatear_numerico_con_ceros(contexto.codigo_ipress, campo[2]),
        3: formatear_numerico_con_ceros(documento.tipo_documento_pago, campo[3]),
        4: formatear_alfanumerico(documento.serie + documento.numero, campo[4]),
        5: formatear_numerico_con_ceros("1", campo[5]),  # una sola prestacion por documento
        6: formatear_numerico_con_ceros(str(procedimiento.correlativo), campo[6]),
        7: formatear_numerico_con_ceros("01", campo[7]),  # CPMS/IEDS (Seccion 8.2)
        8: formatear_alfanumerico(procedimiento.codigo_cpms, campo[8]),
        # La denominacion del catalogo CPMS puede superar largamente los 70
        # caracteres de este campo (verificado en la Fase 4: hasta 922
        # caracteres); se trunca para que encaje, sin fallar la generacion.
        9: formatear_alfanumerico(procedimiento.descripcion[: campo[9].longitud], campo[9]),
        10: formatear_fecha(procedimiento.fecha, campo[10]),
        11: formatear_numerico_con_ceros("00", campo[11]),  # profesional sin colegiatura
        12: " " * campo[12].longitud,
        13: " " * campo[13].longitud,
        14: " " * campo[14].longitud,
        15: formatear_numerico_con_ceros(str(procedimiento.cantidad), campo[15]),
        16: formatear_monto(procedimiento.monto_unitario, campo[16]),
        17: formatear_monto(procedimiento.copago_variable, campo[17]),
        18: formatear_monto(procedimiento.copago_fijo, campo[18]),
        19: formatear_monto(monto_presentado, campo[19]),
        20: formatear_monto(monto_no_cubierto, campo[20]),
        21: " " * campo[21].longitud,  # Diagnostico Asociado: en blanco (CIE-10 no disponible)
        22: formatear_alfanumerico("A", campo[22]),  # Servicio Exento de Impuestos
        23: formatear_numerico_con_ceros("02", campo[23]),  # Codigo Rubro fijo (ver mapeo T3-23)
        24: " " * campo[24].longitud,
        25: " " * campo[25].longitud,
    }


def construir_t4(
    tabla: TablaEsquema,
    contexto: ContextoLote,
    documento: DocumentoLote,
    producto: ProductoLote,
) -> dict[int, str]:
    """T4, Seccion 8.1 (Fase 17): se llama una vez por producto de
    farmacia, no una vez por prestacion (a diferencia de T2). Solo se
    invoca para prestaciones con productos registrados (Anexo 3); una
    prestacion sin productos simplemente no aporta filas a T4."""

    campo = {c.numero: c for c in tabla.campos}
    monto_presentado = (producto.cantidad_venta * producto.monto_unitario).quantize(
        _DOS_DECIMALES, rounding=ROUND_HALF_UP
    )
    # Campo 17: "de no tenerse se consignara el diagnostico principal"
    # (criterio del propio campo, Seccion 8.1 del plan v3).
    diagnostico = (
        producto.diagnostico_asociado_cie10 or documento.prestacion.diagnostico_principal_cie10
    )
    # Campo 19: "de no corresponder se consignara 'XXXXXXXXXXXX'" (criterio C1).
    guia = producto.guia_farmacia or "X" * campo[19].longitud

    return {
        1: formatear_numerico_con_ceros(contexto.ruc_ipress, campo[1]),
        2: formatear_numerico_con_ceros(contexto.codigo_ipress, campo[2]),
        3: formatear_numerico_con_ceros(documento.tipo_documento_pago, campo[3]),
        4: formatear_alfanumerico(documento.serie + documento.numero, campo[4]),
        5: formatear_numerico_con_ceros("1", campo[5]),  # una sola prestacion por documento
        6: formatear_numerico_con_ceros(str(producto.correlativo), campo[6]),
        7: formatear_alfanumerico(producto.tipo_producto, campo[7]),
        8: formatear_numerico_con_ceros(producto.catalogo, campo[8]),
        # GTIN mas corto que 13: relleno de ceros a la izquierda, la
        # convencion GS1 (Anexo 1 no da regla propia; docs/DECISIONES.md).
        9: formatear_numerico_con_ceros(producto.codigo_producto, campo[9]),
        10: formatear_fecha(producto.fecha_dispensacion, campo[10]),
        11: formatear_monto(producto.cantidad_venta, campo[11]),
        12: formatear_numerico_con_ceros(producto.tipo_unidad_dispensacion, campo[12]),
        13: formatear_monto(producto.monto_unitario, campo[13]),
        14: formatear_monto(producto.copago, campo[14]),
        15: formatear_monto(monto_presentado, campo[15]),
        16: formatear_monto(producto.monto_no_cubierto, campo[16]),
        17: formatear_alfanumerico(diagnostico, campo[17]),
        18: formatear_alfanumerico(producto.exento_igv, campo[18]),
        19: formatear_alfanumerico(guia, campo[19]),
        # Cantidad prescrita: opcional, en blanco (mismo supuesto que T3
        # campo 24: no se distingue de la cantidad vendida en este prototipo).
        20: " " * campo[20].longitud,
    }


def _campos_montos_t2(
    procedimientos: tuple[ProcedimientoLote, ...], campo: dict[int, CampoEsquema]
) -> dict[int, str]:
    """Campos 35 a 48 (grupos de gasto): el grupo 1 es la suma de lo
    cubierto por procedimiento; los demas grupos dan 0.00 porque este
    prototipo no modela otras fuentes de cobertura (docs/DECISIONES.md)."""

    gasto_grupo1 = sum((_monto_cubierto(p) for p in procedimientos), _CERO)
    copago_fijo_afecto = sum((p.copago_fijo for p in procedimientos), _CERO)
    copago_variable_afecto = sum((p.copago_variable for p in procedimientos), _CERO)
    total_gastos_cubiertos = gasto_grupo1  # los demas grupos dan 0.00 (ver notas de mapeo)

    return {
        35: formatear_monto(gasto_grupo1, campo[35]),
        36: formatear_monto(_CERO, campo[36]),
        37: formatear_monto(_CERO, campo[37]),
        38: formatear_monto(_CERO, campo[38]),
        39: formatear_monto(_CERO, campo[39]),
        40: formatear_monto(_CERO, campo[40]),
        41: formatear_monto(_CERO, campo[41]),
        42: formatear_monto(_CERO, campo[42]),
        43: formatear_monto(_CERO, campo[43]),
        44: formatear_monto(copago_fijo_afecto, campo[44]),
        45: formatear_monto(_CERO, campo[45]),
        46: formatear_monto(copago_variable_afecto, campo[46]),
        47: formatear_monto(_CERO, campo[47]),
        48: formatear_monto(total_gastos_cubiertos, campo[48]),
    }


def construir_t2(
    tabla: TablaEsquema,
    contexto: ContextoLote,
    documento: DocumentoLote,
    procedimientos: tuple[ProcedimientoLote, ...],
) -> dict[int, str]:
    campo = {c.numero: c for c in tabla.campos}
    prestacion = documento.prestacion

    campos = {
        1: formatear_numerico_con_ceros(contexto.ruc_ipress, campo[1]),
        2: formatear_numerico_con_ceros(contexto.codigo_ipress, campo[2]),
        3: formatear_numerico_con_ceros(documento.tipo_documento_pago, campo[3]),
        4: formatear_alfanumerico(documento.serie + documento.numero, campo[4]),
        5: formatear_numerico_con_ceros("1", campo[5]),
        6: formatear_alfanumerico(prestacion.codigo_prestacion_interno, campo[6]),
        7: formatear_numerico_con_ceros(prestacion.tipo_afiliacion, campo[7]),
        8: formatear_alfanumerico(prestacion.codigo_asegurado, campo[8], derecha=True),
        9: formatear_numerico_con_ceros(prestacion.tipo_documento_paciente, campo[9]),
        10: formatear_alfanumerico(prestacion.numero_documento_paciente, campo[10], derecha=True),
        11: formatear_alfanumerico(prestacion.numero_historia_clinica, campo[11]),
        12: formatear_numerico_con_ceros(prestacion.tipo_documento_autorizacion, campo[12]),
        13: formatear_alfanumerico(prestacion.codigo_autorizacion, campo[13], derecha=True),
        14: formatear_numerico_con_ceros("99", campo[14]),  # sin segundo documento
        15: " " * campo[15].longitud,
        16: formatear_numerico_con_ceros("4", campo[16]),  # Ambulatorio
        # Subtipo Cobertura: PENDIENTE, catalogo SUSALUD no disponible (docs/PENDIENTES.md).
        17: formatear_numerico_con_ceros("0000", campo[17]),
        # Primer Diagnostico: PROVISIONAL, ver mapeo T2-18 y docs/PENDIENTES.md.
        18: formatear_alfanumerico(prestacion.diagnostico_principal_cie10, campo[18]),
        19: " " * campo[19].longitud,
        20: " " * campo[20].longitud,
        21: formatear_fecha(prestacion.fecha_prestacion, campo[21]),
        22: formatear_hora(prestacion.hora_prestacion, campo[22]),
        23: formatear_numerico_con_ceros("00", campo[23]),  # profesional sin colegiatura
        24: " " * campo[24].longitud,
        25: " " * campo[25].longitud,
        26: " " * campo[26].longitud,
        27: formatear_numerico_con_ceros(contexto.ruc_ipress, campo[27]),  # sin derivacion real
        28: " " * campo[28].longitud,
        29: " " * campo[29].longitud,
        30: " " * campo[30].longitud,
        31: " " * campo[31].longitud,
        32: " " * campo[32].longitud,
        33: " " * campo[33].longitud,
        34: " " * campo[34].longitud,
    }
    campos.update(_campos_montos_t2(procedimientos, campo))
    return campos


@dataclass(frozen=True, slots=True)
class _MontosT1:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): los
    montos de T1 (campos 17 a 24), todos derivados de los grupos de gasto
    ya calculados en T2 -- separarlos de `construir_t1` deja esa funcion
    dentro del limite de lineas por funcion (Seccion 3)."""

    exonerado_igv: Decimal
    copago_fijo_afecto: Decimal
    copago_fijo_exonerado: Decimal
    copago_variable_afecto: Decimal
    copago_variable_exonerado: Decimal
    base_imponible: Decimal
    igv: Decimal
    total_facturado: Decimal


def _calcular_montos_t1(
    documento: DocumentoLote, contexto: ContextoLote, valores_t2: dict[int, str]
) -> _MontosT1:
    def _monto_t2(numero: int) -> Decimal:
        return Decimal(valores_t2[numero].strip())

    exonerado_igv = _monto_t2(42)
    copago_fijo_afecto = _monto_t2(44)
    copago_fijo_exonerado = _monto_t2(45)
    copago_variable_afecto = _monto_t2(46)
    copago_variable_exonerado = _monto_t2(47)
    total_gastos_cubiertos = _monto_t2(48)

    base_imponible = (
        total_gastos_cubiertos - exonerado_igv - (copago_fijo_afecto + copago_variable_afecto)
    )
    if base_imponible < 0:
        base_imponible = _CERO  # criterio C4
    if documento.tipo_documento_pago in _TIPOS_DOCUMENTO_SIN_MONTO:
        base_imponible = _CERO  # criterio C6

    igv = (base_imponible * contexto.tasa_igv).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)

    total_facturado = (
        base_imponible + igv + exonerado_igv - (copago_fijo_exonerado + copago_variable_exonerado)
    )
    if documento.tipo_documento_pago in _TIPOS_DOCUMENTO_SIN_MONTO:
        total_facturado = _CERO

    return _MontosT1(
        exonerado_igv=exonerado_igv,
        copago_fijo_afecto=copago_fijo_afecto,
        copago_fijo_exonerado=copago_fijo_exonerado,
        copago_variable_afecto=copago_variable_afecto,
        copago_variable_exonerado=copago_variable_exonerado,
        base_imponible=base_imponible,
        igv=igv,
        total_facturado=total_facturado,
    )


def _campos_nota_t1(nota: NotaLote | None, campo: dict[int, CampoEsquema]) -> dict[int, str]:
    """T1 campos 25 a 29 (RI-11, 2026-11-13): la nota de credito o debito
    del comprobante; sin nota, 'N' y los campos en blanco (criterio C2 de
    cada campo)."""

    if nota is None:
        blancos = {numero: " " * campo[numero].longitud for numero in (26, 27, 28, 29)}
        return {25: formatear_alfanumerico("N", campo[25]), **blancos}
    return {
        25: formatear_alfanumerico(nota.tipo, campo[25]),
        26: formatear_alfanumerico(nota.serie + nota.numero, campo[26]),
        27: formatear_monto(nota.monto, campo[27]),
        28: formatear_fecha(nota.fecha, campo[28]),
        29: formatear_alfanumerico(nota.motivo, campo[29]),
    }


def construir_t1(
    tabla: TablaEsquema,
    contexto: ContextoLote,
    documento: DocumentoLote,
    valores_t2: dict[int, str],
) -> dict[int, str]:
    campo = {c.numero: c for c in tabla.campos}
    m = _calcular_montos_t1(documento, contexto, valores_t2)

    return {
        1: formatear_fecha(contexto.generado_en.date(), campo[1]),
        2: formatear_hora(contexto.generado_en.time(), campo[2]),
        3: formatear_numerico_con_ceros(contexto.numero_lote, campo[3]),
        4: formatear_numerico_con_ceros(contexto.codigo_iafas, campo[4]),
        5: formatear_numerico_con_ceros(contexto.ruc_ipress, campo[5]),
        6: formatear_numerico_con_ceros(contexto.codigo_ipress, campo[6]),
        7: formatear_numerico_con_ceros(documento.tipo_documento_pago, campo[7]),
        8: formatear_alfanumerico(documento.serie + documento.numero, campo[8]),
        9: formatear_fecha(documento.fecha_emision, campo[9]),
        10: formatear_numerico_con_ceros("99999", campo[10]),
        11: formatear_numerico_con_ceros("1", campo[11]),  # una prestacion por documento
        12: formatear_numerico_con_ceros("01", campo[12]),  # pago por servicio
        13: formatear_numerico_con_ceros("999", campo[13]),
        14: formatear_monto(_CERO, campo[14]),
        15: " " * campo[15].longitud,
        16: formatear_numerico_con_ceros("1", campo[16]),  # soles
        17: formatear_monto(m.exonerado_igv, campo[17]),
        18: formatear_monto(m.copago_fijo_afecto, campo[18]),
        19: formatear_monto(m.copago_fijo_exonerado, campo[19]),
        20: formatear_monto(m.copago_variable_afecto, campo[20]),
        21: formatear_monto(m.copago_variable_exonerado, campo[21]),
        22: formatear_monto(m.base_imponible, campo[22]),
        23: formatear_monto(m.igv, campo[23]),
        24: formatear_monto(m.total_facturado, campo[24]),
        **_campos_nota_t1(documento.nota, campo),
        30: formatear_fecha(documento.fecha_primer_envio, campo[30]),
        31: formatear_alfanumerico("N", campo[31]),
    }
