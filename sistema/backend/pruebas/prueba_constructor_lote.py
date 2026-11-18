"""Pruebas del constructor del lote (Seccion 7.2, 7.6) contra el esquema
real: cada tabla construida debe poder escribirse sin error de longitud, y
las formulas citadas del Anexo 1 deben calcular lo esperado."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal

from app.dominio.integracion.lote import (
    ContextoLote,
    DocumentoLote,
    PrestacionLote,
    ProcedimientoLote,
    ProductoLote,
)
from app.infraestructura.tedef.carga_esquema import cargar_esquema
from app.infraestructura.tedef.constructor_lote import (
    construir_t1,
    construir_t2,
    construir_t3,
    construir_t4,
)
from app.infraestructura.tedef.escritor_ancho_fijo import escribir_registro
from app.infraestructura.tedef.montos_lote import calcular_gastos, calcular_montos_facturados

_ESQUEMA = cargar_esquema()


def _contexto() -> ContextoLote:
    return ContextoLote(
        numero_lote="0000001",
        periodo="202609",
        generado_en=datetime(2026, 9, 16, 8, 30, 0),
        ruc_ipress="20123456789",
        codigo_ipress="12345678",
        codigo_iafas="00012",
        tasa_igv=Decimal("0.18"),
    )


def _documento(procedimientos: tuple[ProcedimientoLote, ...]) -> DocumentoLote:
    prestacion = PrestacionLote(
        codigo_prestacion_interno="CTA-000001",
        numero_historia_clinica="00000001",
        tipo_documento_paciente="1",
        numero_documento_paciente="12345678",
        codigo_asegurado="AS000001",
        tipo_afiliacion="1",
        codigo_autorizacion="AUT0000001",
        tipo_documento_autorizacion="03",
        fecha_prestacion=date(2026, 9, 15),
        hora_prestacion=time(9, 0, 0),
        diagnostico_principal_cie10="E119",
        procedimientos=procedimientos,
    )
    return DocumentoLote(
        documento_id=1,
        cuenta_medica_id=1,
        tipo_documento_pago="01",
        serie="F001",
        numero="00000123",
        fecha_emision=date(2026, 9, 15),
        fecha_primer_envio=None,
        prestacion=prestacion,
    )


def _procedimiento(
    cantidad: int,
    monto_unitario: str,
    copago_variable: str = "0.00",
    copago_fijo: str = "0.00",
) -> ProcedimientoLote:
    return ProcedimientoLote(
        correlativo=1,
        codigo_cpms="00100",
        descripcion="Procedimiento de prueba",
        fecha=date(2026, 9, 15),
        cantidad=cantidad,
        monto_unitario=Decimal(monto_unitario),
        copago_variable=Decimal(copago_variable),
        copago_fijo=Decimal(copago_fijo),
    )


def prueba_t3_se_escribe_sin_error_de_longitud() -> None:
    procedimiento = _procedimiento(2, "50.00")
    documento = _documento((procedimiento,))
    valores = construir_t3(_ESQUEMA["T3"], _contexto(), documento, procedimiento)
    linea = escribir_registro(_ESQUEMA["T3"], valores)
    assert len(linea) == _ESQUEMA["T3"].longitud_registro


def prueba_t3_monto_presentado_es_cantidad_por_monto_unitario() -> None:
    procedimiento = _procedimiento(3, "25.50")
    documento = _documento((procedimiento,))
    valores = construir_t3(_ESQUEMA["T3"], _contexto(), documento, procedimiento)
    assert valores[19].strip() == "76.50"  # 3 * 25.50


def prueba_t3_monto_no_cubierto_es_la_suma_de_los_copagos() -> None:
    procedimiento = _procedimiento(1, "100.00", copago_variable="10.00", copago_fijo="5.00")
    documento = _documento((procedimiento,))
    valores = construir_t3(_ESQUEMA["T3"], _contexto(), documento, procedimiento)
    assert valores[20].strip() == "15.00"


def _producto(cantidad_venta: str, monto_unitario: str) -> ProductoLote:
    return ProductoLote(
        correlativo=1,
        tipo_producto="M",
        catalogo="1",
        codigo_producto="0380652555906",
        fecha_dispensacion=date(2026, 9, 15),
        cantidad_venta=Decimal(cantidad_venta),
        tipo_unidad_dispensacion="1",
        monto_unitario=Decimal(monto_unitario),
        copago=Decimal("0.00"),
        monto_no_cubierto=Decimal("0.00"),
        diagnostico_asociado_cie10=None,
        exento_igv="A",
        guia_farmacia=None,
        cantidad_prescrita=None,
    )


def prueba_t4_se_escribe_sin_error_de_longitud() -> None:
    producto = _producto("1", "15.50")
    documento = _documento(())
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    linea = escribir_registro(_ESQUEMA["T4"], valores)
    assert len(linea) == _ESQUEMA["T4"].longitud_registro


def prueba_t4_monto_presentado_es_cantidad_por_monto_unitario() -> None:
    producto = _producto("3", "28.50")
    documento = _documento(())
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    assert valores[15].strip() == "85.50"  # 3 * 28.50


def prueba_t4_codigo_gtin_mas_corto_se_rellena_con_ceros_a_la_izquierda() -> None:
    # GTIN-12 (12 caracteres) en un campo de 13: relleno de un cero a la
    # izquierda, convencion GS1 (docs/DECISIONES.md, Fase 17).
    producto = replace(_producto("1", "15.50"), codigo_producto="008400001344")
    documento = _documento(())
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    assert valores[9] == "0008400001344"


def prueba_t4_usa_el_diagnostico_principal_cuando_el_producto_no_trae_el_suyo() -> None:
    producto = _producto("1", "15.50")  # diagnostico_asociado_cie10=None
    documento = _documento(())  # diagnostico_principal_cie10="E119"
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    assert valores[17].strip() == "E119"


def prueba_t4_usa_el_diagnostico_propio_del_producto_si_lo_trae() -> None:
    producto = replace(_producto("1", "15.50"), diagnostico_asociado_cie10="J209")
    documento = _documento(())  # diagnostico_principal_cie10="E119"
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    assert valores[17].strip() == "J209"


def prueba_t4_guia_de_farmacia_se_rellena_con_x_cuando_no_corresponde() -> None:
    producto = _producto("1", "15.50")  # guia_farmacia=None
    documento = _documento(())
    valores = construir_t4(_ESQUEMA["T4"], _contexto(), documento, producto)
    assert valores[19].strip() == "X" * len(valores[19].strip())


def prueba_t2_se_escribe_sin_error_de_longitud() -> None:
    procedimiento = _procedimiento(1, "80.00")
    documento = _documento((procedimiento,))
    valores = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    linea = escribir_registro(_ESQUEMA["T2"], valores)
    assert len(linea) == _ESQUEMA["T2"].longitud_registro


def prueba_t2_total_gastos_cubiertos_neta_los_copagos() -> None:
    procedimientos = (
        _procedimiento(1, "100.00", copago_variable="10.00"),
        _procedimiento(2, "50.00", copago_fijo="5.00"),  # monto presentado 100.00
    )
    documento = _documento(procedimientos)
    valores = construir_t2(_ESQUEMA["T2"], _contexto(), documento, procedimientos)
    # cubierto = (100-10) + (100-5) = 90 + 95 = 185.00
    assert valores[48].strip() == "185.00"
    assert valores[35].strip() == valores[48].strip()  # todo cae en el grupo 1 (rubro fijo '02')
    assert valores[44].strip() == "5.00"  # copago fijo afecto
    assert valores[46].strip() == "10.00"  # copago variable afecto


def prueba_t1_se_escribe_sin_error_de_longitud() -> None:
    procedimiento = _procedimiento(1, "100.00")
    documento = _documento((procedimiento,))
    valores_t2 = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    valores_t1 = construir_t1(_ESQUEMA["T1"], _contexto(), documento, valores_t2)
    linea = escribir_registro(_ESQUEMA["T1"], valores_t1)
    assert len(linea) == _ESQUEMA["T1"].longitud_registro


def prueba_t1_base_imponible_e_igv() -> None:
    procedimiento = _procedimiento(1, "100.00")  # sin copagos: total cubierto = 100.00
    documento = _documento((procedimiento,))
    valores_t2 = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    valores_t1 = construir_t1(_ESQUEMA["T1"], _contexto(), documento, valores_t2)
    # base_imponible = 100.00 - 0.00 - (0.00+0.00) = 100.00
    assert valores_t1[22].strip() == "100.00"
    # igv = 100.00 * 0.18 = 18.00
    assert valores_t1[23].strip() == "18.00"
    # monto_total = 100.00 + 18.00 + 0.00 - (0.00+0.00) = 118.00
    assert valores_t1[24].strip() == "118.00"


def prueba_t1_tipo_documento_10_fuerza_montos_en_cero() -> None:
    procedimiento = _procedimiento(1, "100.00")
    documento = _documento((procedimiento,))
    documento = DocumentoLote(
        documento_id=documento.documento_id,
        cuenta_medica_id=documento.cuenta_medica_id,
        tipo_documento_pago="10",  # FUA: criterio C6
        serie=documento.serie,
        numero=documento.numero,
        fecha_emision=documento.fecha_emision,
        fecha_primer_envio=documento.fecha_primer_envio,
        prestacion=documento.prestacion,
    )
    valores_t2 = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    valores_t1 = construir_t1(_ESQUEMA["T1"], _contexto(), documento, valores_t2)
    assert valores_t1[22].strip() == "0.00"
    assert valores_t1[24].strip() == "0.00"


def _documento_con_farmacia(
    procedimientos: tuple[ProcedimientoLote, ...], productos: tuple[ProductoLote, ...]
) -> DocumentoLote:
    documento = _documento(procedimientos)
    return replace(documento, prestacion=replace(documento.prestacion, productos=productos))


def prueba_t2_la_farmacia_suma_al_total_de_gastos_cubiertos() -> None:
    # Criterio C3 del campo 40: T4 suma (presentado - no cubierto) de los
    # productos no exonerados. Hasta el 2026-11-18 iba siempre en 0.00.
    procedimiento = _procedimiento(1, "100.00", copago_variable="20.00")
    producto = replace(
        _producto("2", "25.00"), copago=Decimal("8.00"), monto_no_cubierto=Decimal("10.00")
    )
    documento = _documento_con_farmacia((procedimiento,), (producto,))
    valores = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    assert valores[35].strip() == "80.00"  # 100.00 - 20.00
    assert valores[40].strip() == "40.00"  # 2 * 25.00 - 10.00
    assert valores[42].strip() == "0.00"
    assert valores[46].strip() == "28.00"  # copago del procedimiento y del producto
    assert valores[48].strip() == "120.00"


def prueba_t2_la_farmacia_exonerada_va_al_campo_de_exonerados() -> None:
    procedimiento = _procedimiento(1, "100.00")
    producto = replace(_producto("1", "50.00"), exento_igv="D", copago=Decimal("5.00"))
    documento = _documento_con_farmacia((procedimiento,), (producto,))
    valores = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    assert valores[40].strip() == "0.00"
    assert valores[42].strip() == "50.00"
    assert valores[47].strip() == "5.00"
    assert valores[48].strip() == "150.00"


def prueba_t1_factura_la_farmacia_con_la_misma_regla() -> None:
    procedimiento = _procedimiento(1, "100.00")
    afecto = _producto("1", "50.00")
    exonerado = replace(_producto("1", "30.00"), correlativo=2, exento_igv="D")
    documento = _documento_con_farmacia((procedimiento,), (afecto, exonerado))
    valores_t2 = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    valores = construir_t1(_ESQUEMA["T1"], _contexto(), documento, valores_t2)
    assert valores[17].strip() == "30.00"  # exonerado de IGV
    assert valores[22].strip() == "150.00"  # base imponible: 180.00 - 30.00
    assert valores[23].strip() == "27.00"  # 18 % de 150.00
    assert valores[24].strip() == "207.00"  # 150.00 + 27.00 + 30.00


def prueba_el_comprobante_cobra_la_farmacia() -> None:
    procedimiento = _procedimiento(1, "100.00")
    exonerado = replace(_producto("1", "30.00"), exento_igv="D")
    gastos = calcular_gastos((procedimiento,), (_producto("1", "50.00"), exonerado))
    montos = calcular_montos_facturados("01", gastos, Decimal("0.18"))
    assert montos.total_facturado == Decimal("207.00")
    assert montos.igv == Decimal("27.00")
    # Valor de venta mas IGV da el total aunque haya productos exonerados.
    assert montos.valor_venta + montos.igv == montos.total_facturado
