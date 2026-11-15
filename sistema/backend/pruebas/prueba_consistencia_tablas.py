"""Pruebas de consistencia entre tablas (Seccion 7.5, Seccion 12.2:
'Lote con ruptura de llave')."""

from __future__ import annotations

from app.infraestructura.tedef.consistencia_tablas import validar_consistencia

_RUC = "20123456789"
_IPRESS = "12345678"
_IAFAS = "00012"
_LOTE = "0000001"
_TIPO_DOC = "01"
_NUMERO_DOC = "F0010000001"


def _fila_t1(cantidad_prestaciones: str = "1") -> dict[int, str]:
    return {
        3: _LOTE,
        4: _IAFAS,
        5: _RUC,
        6: _IPRESS,
        7: _TIPO_DOC,
        8: _NUMERO_DOC,
        11: cantidad_prestaciones,
    }


def _fila_t2(correlativo_prestacion: str = "1") -> dict[int, str]:
    return {1: _RUC, 2: _IPRESS, 3: _TIPO_DOC, 4: _NUMERO_DOC, 5: correlativo_prestacion}


def _fila_t3(correlativo_prestacion: str = "1", correlativo_servicio: str = "1") -> dict[int, str]:
    return {
        1: _RUC,
        2: _IPRESS,
        3: _TIPO_DOC,
        4: _NUMERO_DOC,
        5: correlativo_prestacion,
        6: correlativo_servicio,
    }


def _fila_t4(correlativo_prestacion: str = "1", correlativo_producto: str = "1") -> dict[int, str]:
    return {
        1: _RUC,
        2: _IPRESS,
        3: _TIPO_DOC,
        4: _NUMERO_DOC,
        5: correlativo_prestacion,
        6: correlativo_producto,
    }


def prueba_lote_consistente_no_produce_hallazgos() -> None:
    hallazgos = validar_consistencia([_fila_t1()], [_fila_t2()], [_fila_t3()], [])
    assert hallazgos == []


def prueba_lote_consistente_con_productos_no_produce_hallazgos() -> None:
    hallazgos = validar_consistencia([_fila_t1()], [_fila_t2()], [_fila_t3()], [_fila_t4()])
    assert hallazgos == []


def prueba_documento_sin_prestacion_en_t2_es_detectado() -> None:
    hallazgos = validar_consistencia([_fila_t1()], [], [], [])
    assert any(h.tabla == "T1" and "sin ninguna prestacion" in h.mensaje for h in hallazgos)


def prueba_cantidad_de_prestaciones_declarada_no_coincide() -> None:
    fila_t1 = _fila_t1(cantidad_prestaciones="2")
    hallazgos = validar_consistencia([fila_t1], [_fila_t2()], [_fila_t3()], [])
    assert any(h.campo_numero == 11 for h in hallazgos)


def prueba_llave_primaria_t1_duplicada_es_detectada() -> None:
    hallazgos = validar_consistencia([_fila_t1(), _fila_t1()], [_fila_t2()], [_fila_t3()], [])
    assert any("duplicada" in h.mensaje for h in hallazgos)


def prueba_procedimiento_sin_prestacion_correspondiente_es_detectado() -> None:
    fila_t3_huerfana = _fila_t3(correlativo_prestacion="9")
    hallazgos = validar_consistencia([_fila_t1()], [_fila_t2()], [fila_t3_huerfana], [])
    assert any(h.tabla == "T3" and "sin prestacion T2" in h.mensaje for h in hallazgos)


def prueba_correlativos_de_servicio_no_ascendentes_son_detectados() -> None:
    filas_t3 = [_fila_t3(correlativo_servicio="1"), _fila_t3(correlativo_servicio="3")]
    hallazgos = validar_consistencia(
        [_fila_t1(cantidad_prestaciones="1")], [_fila_t2()], filas_t3, []
    )
    assert any(h.tabla == "T3" and h.campo_numero == 6 for h in hallazgos)


def prueba_producto_sin_prestacion_correspondiente_es_detectado() -> None:
    fila_t4_huerfana = _fila_t4(correlativo_prestacion="9")
    hallazgos = validar_consistencia([_fila_t1()], [_fila_t2()], [], [fila_t4_huerfana])
    assert any(h.tabla == "T4" and "sin prestacion T2" in h.mensaje for h in hallazgos)


def prueba_correlativos_de_producto_no_ascendentes_son_detectados() -> None:
    filas_t4 = [_fila_t4(correlativo_producto="1"), _fila_t4(correlativo_producto="3")]
    hallazgos = validar_consistencia(
        [_fila_t1(cantidad_prestaciones="1")], [_fila_t2()], [], filas_t4
    )
    assert any(h.tabla == "T4" and h.campo_numero == 6 for h in hallazgos)
