"""Pruebas de integracion del validador de campo (Seccion 7.6, 7.7) contra
el esquema real cargado desde configuracion/esquema_tedef/esquema_2025_10.yaml."""

from __future__ import annotations

from app.infraestructura.tedef.carga_esquema import cargar_esquema
from app.infraestructura.tedef.validador_campo import validar_registro

_ESQUEMA = cargar_esquema()


def _fila_t1_conforme() -> dict[int, str]:
    """Una fila T1 completa, ancho fijo, que no deberia producir errores
    en los criterios que la Fase 6 implementa (estructurales, fecha, hora,
    RUC, solo digitos, dominio, fecha_no_posterior_a)."""

    tabla = _ESQUEMA["T1"]
    valores = {
        1: "20260915",  # Fecha de envio
        2: "083000",  # Hora de envio
        3: "0000001",  # Numero de lote
        4: "00012",  # Codigo IAFAS
        5: "20123456789",  # RUC
        6: "12345678",  # Codigo IPRESS
        7: "01",  # Tipo Documento de Pago (dominio)
        8: "F00100000123",  # Numero de Documento de Pago (4 serie + 8 numero)
        9: "20260910",  # Fecha de Emision (<= fecha de envio)
        10: "99999",  # Producto
        11: "00001",  # Cantidad de prestaciones
        12: "01",  # Mecanismo de Pago (dominio)
        13: "999",  # Sub Tipo Mecanismo de Pago
        14: "        0.00",  # Monto Pre Pactado
        15: "        ",  # Fecha inicio Periodo Pre Pactado (blanco, opcional)
        16: "1",  # Tipo de moneda
        17: "        0.00",
        18: "        0.00",
        19: "        0.00",
        20: "        0.00",
        21: "        0.00",
        22: "      100.00",  # Base imponible
        23: "       18.00",  # IGV
        24: "      118.00",  # Monto Total Facturado
        25: "N",  # Tipo identificacion Nota (dominio)
        26: "            ",
        27: "            ",
        28: "        ",
        29: " ",
        30: "        ",
        31: "N",  # Indicador Factura Global (dominio)
    }
    assert set(valores) == {c.numero for c in tabla.campos}
    return valores


def prueba_fila_t1_conforme_no_produce_errores_en_lo_implementado() -> None:
    hallazgos = validar_registro(_ESQUEMA["T1"], _fila_t1_conforme())
    errores = [h for h in hallazgos if h.severidad == "error"]
    assert errores == []


def prueba_detecta_fecha_invalida() -> None:
    fila = _fila_t1_conforme()
    fila[1] = "20261332"  # mes 13 invalido
    hallazgos = validar_registro(_ESQUEMA["T1"], fila)
    assert any(h.campo_numero == 1 and h.severidad == "error" for h in hallazgos)


def prueba_detecta_campo_obligatorio_vacio() -> None:
    fila = _fila_t1_conforme()
    fila[3] = "       "  # Numero de Lote (obligatorio) vacio
    hallazgos = validar_registro(_ESQUEMA["T1"], fila)
    assert any(h.campo_numero == 3 and "obligatorio" in h.mensaje.lower() for h in hallazgos)


def prueba_detecta_longitud_incorrecta() -> None:
    fila = _fila_t1_conforme()
    fila[6] = "1234567"  # Codigo IPRESS con 7 caracteres, no 8
    hallazgos = validar_registro(_ESQUEMA["T1"], fila)
    assert any(h.campo_numero == 6 and "longitud" in h.mensaje.lower() for h in hallazgos)


def prueba_detecta_fecha_emision_posterior_a_envio() -> None:
    fila = _fila_t1_conforme()
    fila[9] = "20260920"  # posterior a la fecha de envio (campo 1)
    hallazgos = validar_registro(_ESQUEMA["T1"], fila)
    assert any(h.campo_numero == 9 and h.criterio_id == "C2" for h in hallazgos)


def prueba_detecta_valor_fuera_de_dominio() -> None:
    fila = _fila_t1_conforme()
    fila[7] = "77"  # Tipo Documento de Pago fuera del dominio
    hallazgos = validar_registro(_ESQUEMA["T1"], fila)
    coincidencias = [h for h in hallazgos if h.campo_numero == 7]
    assert coincidencias
    # El dominio de T1 campo 7 esta sin confirmar (Seccion 7.4): advertencia, no error.
    assert coincidencias[0].severidad == "advertencia"


def prueba_t2_suma_igual_a_detecta_inconsistencia() -> None:
    tabla = _ESQUEMA["T2"]
    fila = {c.numero: "        0.00" for c in tabla.campos if c.decimales == 2}
    for c in tabla.campos:
        if c.numero not in fila:
            fila[c.numero] = " " * c.longitud if not c.obligatorio else "0" * c.longitud
    fila[48] = "      999.99"  # no coincide con la suma (todo 0.00)
    hallazgos = validar_registro(tabla, fila)
    assert any(h.campo_numero == 48 and h.criterio_id == "C1" for h in hallazgos)


def prueba_t3_producto_con_tolerancia_detecta_inconsistencia() -> None:
    tabla = _ESQUEMA["T3"]
    fila = {c.numero: " " * c.longitud for c in tabla.campos}
    fila[15] = "00003"  # numero de veces
    fila[16] = "      10.00"  # monto unitario
    fila[19] = "        1.00"  # deberia ser ~30.00
    hallazgos = validar_registro(tabla, fila)
    assert any(h.campo_numero == 19 and h.criterio_id == "C3" for h in hallazgos)


def _fila_t4_conforme() -> dict[int, str]:
    """Fila T4 completa, ancho fijo, que no deberia producir errores en
    los criterios que la Fase 17 implementa (estructurales, ruc, fecha,
    dominio, solo_digitos, producto_con_tolerancia)."""

    tabla = _ESQUEMA["T4"]
    valores = {
        1: "20123456789",  # RUC
        2: "12345678",  # Codigo IPRESS
        3: "01",  # Tipo Documento de Pago (dominio)
        4: "F00100000123",  # Numero de Documento de Pago
        5: "00001",  # Correlativo de la prestacion
        6: "0001",  # Correlativo del producto de farmacia
        7: "M",  # Tipo de producto (dominio)
        8: "1",  # Catalogo (dominio, GTIN)
        9: "0380652555906",  # Codigo de producto (GTIN-13)
        10: "20260915",  # Fecha de dispensacion
        11: "   1.00",  # Cantidad de venta (decimales=2)
        12: "1",  # Tipo de unidad de dispensacion (dominio)
        13: "       15.50",  # Monto unitario sin impuesto
        14: "        0.00",  # Copago
        15: "       15.50",  # Monto presentado (1 * 15.50)
        16: "        0.00",  # Monto no cubierto
        17: "E119 ",  # Diagnostico asociado
        18: "A",  # Exento de IGV (dominio)
        19: "XXXXXXXXXXXX",  # Guia de farmacia: no corresponde
        20: "       ",  # Cantidad prescrita (opcional, en blanco)
    }
    assert set(valores) == {c.numero for c in tabla.campos}
    return valores


def prueba_fila_t4_conforme_no_produce_errores_en_lo_implementado() -> None:
    hallazgos = validar_registro(_ESQUEMA["T4"], _fila_t4_conforme())
    errores = [h for h in hallazgos if h.severidad == "error"]
    assert errores == []


def prueba_t4_campo_11_decimales_acepta_valor_con_punto() -> None:
    # Regresion: T4 campo 11 ("Cantidad de Venta del Producto") declara
    # decimales=2, a diferencia de los demas campos "solo digitos" de
    # esta lista -- su C1 no esta implementado via SoloDigitos (que
    # rechazaria el punto decimal); lo cubre el chequeo estructural
    # MontoDosDecimales (docs/DECISIONES.md, Fase 17).
    fila = _fila_t4_conforme()
    assert "." in fila[11]
    hallazgos = validar_registro(_ESQUEMA["T4"], fila)
    assert not any(h.campo_numero == 11 for h in hallazgos)


def prueba_t4_producto_con_tolerancia_detecta_inconsistencia() -> None:
    fila = dict(_fila_t4_conforme())
    fila[15] = "1.00".rjust(len(fila[15]))  # deberia ser ~15.50 (1 x 15.50)
    hallazgos = validar_registro(_ESQUEMA["T4"], fila)
    assert any(h.campo_numero == 15 and h.criterio_id == "C4" for h in hallazgos)
