"""Pruebas del motor de orquestacion (R2.4/R2.5/R2.6, Seccion 5.2.4):
las diecisiete transiciones de la Tabla 58/65/66, una por una, y las
reglas de rechazo de la Tabla 69 (secuencia de flujo)."""

from __future__ import annotations

import pytest

from app.dominio.orquestacion.errores import ErrorAnulacionSinAprobacion, ErrorTransicionNoDefinida
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES, TipoTransicion

# Las diecisiete filas de la Tabla 58 (y su detalle en 65/66), en el
# mismo orden y numeracion que la tesis. ANULACION (fila 17) se prueba
# aparte, porque no tiene un unico estado previo fijo.
_TRANSICIONES_DEFINIDAS = [
    (None, TipoTransicion.REGISTRO, "REGISTRADA"),  # 1
    ("REGISTRADA", TipoTransicion.FACTURACION, "FACTURADA"),  # 2
    ("FACTURADA", TipoTransicion.REMISION, "ENVIADA"),  # 3
    ("ENVIADA", TipoTransicion.INICIO_AUDITORIA, "EN_AUDITORIA"),  # 4
    ("EN_AUDITORIA", TipoTransicion.LIQUIDACION, "LIQUIDADA"),  # 5a
    ("EN_AUDITORIA", TipoTransicion.GLOSA, "GLOSADA"),  # 5b
    ("GLOSADA", TipoTransicion.SUBSANACION, "SUBSANADA"),  # 6
    ("SUBSANADA", TipoTransicion.LIQUIDACION, "LIQUIDADA"),  # 7
    ("LIQUIDADA", TipoTransicion.CONCILIACION_PAGO, "PAGADA"),  # 8
    ("PAGADA", TipoTransicion.CIERRE, "CERRADA"),  # 9
    ("ENVIADA", TipoTransicion.RECHAZO_LOTE, "RECHAZADA"),  # 10
    ("RECHAZADA", TipoTransicion.CORRECCION_REENVIO, "FACTURADA"),  # 11
    ("EN_AUDITORIA", TipoTransicion.GLOSA_PARCIAL, "GLOSADA_PARCIAL"),  # 12
    ("GLOSADA_PARCIAL", TipoTransicion.LIQUIDACION_PARCIAL, "LIQUIDADA_PARCIAL"),  # 13
    ("SUBSANADA", TipoTransicion.NUEVA_OBSERVACION, "GLOSADA"),  # 14
    ("LIQUIDADA_PARCIAL", TipoTransicion.CONCILIACION_PAGO_PARCIAL, "PAGADA_PARCIAL"),  # 15
    ("PAGADA_PARCIAL", TipoTransicion.CIERRE, "CERRADA"),  # 16
]


@pytest.mark.parametrize(
    ("estado_previo", "transicion", "estado_nuevo_esperado"), _TRANSICIONES_DEFINIDAS
)
def prueba_cada_transicion_definida_produce_su_estado_resultante(
    estado_previo: str | None, transicion: TipoTransicion, estado_nuevo_esperado: str
) -> None:
    assert validar_transicion(estado_previo, transicion) == estado_nuevo_esperado


def prueba_las_diecisiete_filas_de_la_tabla_58_estan_cubiertas() -> None:
    """Filas 1 a 16 (la 5 cuenta como dos, 5a y 5b) con estado previo
    fijo, mas la fila 17 (ANULACION, sin estado previo fijo: probada
    aparte, mas abajo) completan las diecisiete de la Tabla 58."""

    assert len(_TRANSICIONES_DEFINIDAS) == 17


@pytest.mark.parametrize(
    ("estado_previo", "transicion"),
    [
        ("REGISTRADA", TipoTransicion.REMISION),
        ("FACTURADA", TipoTransicion.INICIO_AUDITORIA),
        ("ENVIADA", TipoTransicion.FACTURACION),
        ("GLOSADA", TipoTransicion.CONCILIACION_PAGO),
        (None, TipoTransicion.FACTURACION),
    ],
)
def prueba_transicion_no_definida_es_rechazada(
    estado_previo: str | None, transicion: TipoTransicion
) -> None:
    with pytest.raises(ErrorTransicionNoDefinida):
        validar_transicion(estado_previo, transicion)


@pytest.mark.parametrize("estado_terminal", sorted(ESTADOS_TERMINALES))
def prueba_ningun_estado_terminal_admite_nuevas_transiciones(estado_terminal: str) -> None:
    for transicion in TipoTransicion:
        if transicion is TipoTransicion.ANULACION:
            continue
        with pytest.raises(ErrorTransicionNoDefinida):
            validar_transicion(estado_terminal, transicion)


# --- Anulacion (fila 17, RF-21): desde cualquier estado no terminal, y
# solo con la aprobacion del jefe de cuentas medicas -----------------


@pytest.mark.parametrize(
    "estado_no_terminal",
    [
        "REGISTRADA",
        "FACTURADA",
        "ENVIADA",
        "EN_AUDITORIA",
        "GLOSADA",
        "GLOSADA_PARCIAL",
        "SUBSANADA",
        "LIQUIDADA",
        "LIQUIDADA_PARCIAL",
        "PAGADA",
        "PAGADA_PARCIAL",
        "RECHAZADA",
    ],
)
def prueba_anulacion_aprobada_procede_desde_cualquier_estado_no_terminal(
    estado_no_terminal: str,
) -> None:
    assert (
        validar_transicion(estado_no_terminal, TipoTransicion.ANULACION, aprobacion_anulacion=True)
        == "ANULADA"
    )


def prueba_anulacion_sin_aprobacion_es_rechazada() -> None:
    with pytest.raises(ErrorAnulacionSinAprobacion):
        validar_transicion("REGISTRADA", TipoTransicion.ANULACION)


@pytest.mark.parametrize("estado_terminal", sorted(ESTADOS_TERMINALES))
def prueba_anulacion_desde_un_estado_terminal_es_rechazada(estado_terminal: str) -> None:
    with pytest.raises(ErrorTransicionNoDefinida):
        validar_transicion(estado_terminal, TipoTransicion.ANULACION, aprobacion_anulacion=True)


def prueba_anulacion_de_una_cuenta_nunca_registrada_es_rechazada() -> None:
    with pytest.raises(ErrorTransicionNoDefinida):
        validar_transicion(None, TipoTransicion.ANULACION, aprobacion_anulacion=True)
