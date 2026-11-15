"""Valores del motor de orquestacion (Seccion 5.2.4, R2.4/R2.5): los
catorce estados de la cuenta medica y las diecisiete transiciones
admitidas entre ellos (Tabla 58, y su detalle en Tabla 65 y Tabla 66 de
la Seccion 6.2.2 -- la misma tabla, presentada dos veces en la tesis con
la misma numeracion 1 a 17).

Nombres de transicion en snake_case/mayusculas, uno por fila de la
Tabla 58; no son los mismos nombres que los `tipo_evento` que se
guardan en el almacen de eventos (esos son mas descriptivos, Seccion
6.1: "accion realizada"), son el identificador interno de la regla."""

from __future__ import annotations

from enum import StrEnum

# Seccion 5.2.4: "Los estados CERRADA y ANULADA son terminales: una
# cuenta que los alcanza no admite nuevas transiciones."
ESTADOS_TERMINALES = frozenset({"CERRADA", "ANULADA"})


class TipoTransicion(StrEnum):
    """Una entrada por fila de la Tabla 58 (T-01 a T-13 mas las
    subdivisiones 5a/5b y 10 a 17 de la Tabla 65/66)."""

    REGISTRO = "REGISTRO"  # T-01
    FACTURACION = "FACTURACION"  # T-02
    REMISION = "REMISION"  # T-03
    RECHAZO_LOTE = "RECHAZO_LOTE"  # T-04 (fila 10)
    CORRECCION_REENVIO = "CORRECCION_REENVIO"  # T-05 (fila 11)
    INICIO_AUDITORIA = "INICIO_AUDITORIA"  # T-06 (fila 4)
    GLOSA = "GLOSA"  # T-07 (fila 5b, observacion total)
    GLOSA_PARCIAL = "GLOSA_PARCIAL"  # T-07 (fila 12, observacion parcial)
    SUBSANACION = "SUBSANACION"  # T-08 (fila 6)
    NUEVA_OBSERVACION = "NUEVA_OBSERVACION"  # T-09 (fila 14)
    LIQUIDACION = "LIQUIDACION"  # T-10 (filas 5a y 7, liquidacion total)
    LIQUIDACION_PARCIAL = "LIQUIDACION_PARCIAL"  # T-10 (fila 13)
    CONCILIACION_PAGO = "CONCILIACION_PAGO"  # T-11 (fila 8, pago total)
    CONCILIACION_PAGO_PARCIAL = "CONCILIACION_PAGO_PARCIAL"  # T-11 (fila 15)
    CIERRE = "CIERRE"  # T-12 (filas 9 y 16)
    ANULACION = "ANULACION"  # T-13 (fila 17)


# (estado_previo, transicion) -> estado_nuevo. `None` como estado_previo
# solo aparece en la fila 1 (Tabla 65): "el primer evento de un agregado
# debe ser su registro inicial, cuyo estado previo es vacio" (Tabla 69).
#
# ANULACION no esta en este mapa: la Tabla 58 la define desde "un estado
# no terminal" (cualquiera de los doce no terminales), no desde uno
# fijo -- `motor.validar_transicion` la trata aparte, en vez de repetir
# la misma fila doce veces. Publico (sin guion bajo) porque
# `motor.py`, el unico consumidor, es su complemento directo: juntos
# son la especificacion completa de la Tabla 58.
TRANSICIONES: dict[tuple[str | None, TipoTransicion], str] = {
    (None, TipoTransicion.REGISTRO): "REGISTRADA",
    ("REGISTRADA", TipoTransicion.FACTURACION): "FACTURADA",
    ("FACTURADA", TipoTransicion.REMISION): "ENVIADA",
    ("ENVIADA", TipoTransicion.RECHAZO_LOTE): "RECHAZADA",
    ("RECHAZADA", TipoTransicion.CORRECCION_REENVIO): "FACTURADA",
    ("ENVIADA", TipoTransicion.INICIO_AUDITORIA): "EN_AUDITORIA",
    ("EN_AUDITORIA", TipoTransicion.GLOSA): "GLOSADA",
    ("EN_AUDITORIA", TipoTransicion.GLOSA_PARCIAL): "GLOSADA_PARCIAL",
    ("GLOSADA", TipoTransicion.SUBSANACION): "SUBSANADA",
    ("SUBSANADA", TipoTransicion.NUEVA_OBSERVACION): "GLOSADA",
    ("EN_AUDITORIA", TipoTransicion.LIQUIDACION): "LIQUIDADA",
    ("SUBSANADA", TipoTransicion.LIQUIDACION): "LIQUIDADA",
    ("GLOSADA_PARCIAL", TipoTransicion.LIQUIDACION_PARCIAL): "LIQUIDADA_PARCIAL",
    ("LIQUIDADA", TipoTransicion.CONCILIACION_PAGO): "PAGADA",
    ("LIQUIDADA_PARCIAL", TipoTransicion.CONCILIACION_PAGO_PARCIAL): "PAGADA_PARCIAL",
    ("PAGADA", TipoTransicion.CIERRE): "CERRADA",
    ("PAGADA_PARCIAL", TipoTransicion.CIERRE): "CERRADA",
}


class EtapaCiclo(StrEnum):
    """Las cuatro etapas del ciclo de la cuenta medica que describe la tesis
    (Seccion 5.2.1: admision, facturacion, auditoria y liquidacion) mas las
    anuladas. Agrupan los catorce estados de la Tabla 58 para filtrar la
    bandeja sin exponer al usuario catorce opciones (2026-11-12): los
    estados se conservan en el motor y en la trazabilidad (R2.4)."""

    ADMISION = "ADMISION"
    FACTURACION = "FACTURACION"
    AUDITORIA = "AUDITORIA"
    LIQUIDACION = "LIQUIDACION"
    ANULADA = "ANULADA"


ESTADOS_POR_ETAPA: dict[EtapaCiclo, tuple[str, ...]] = {
    EtapaCiclo.ADMISION: ("REGISTRADA",),
    EtapaCiclo.FACTURACION: ("FACTURADA", "ENVIADA", "RECHAZADA"),
    EtapaCiclo.AUDITORIA: ("EN_AUDITORIA", "GLOSADA", "GLOSADA_PARCIAL", "SUBSANADA"),
    EtapaCiclo.LIQUIDACION: (
        "LIQUIDADA",
        "LIQUIDADA_PARCIAL",
        "PAGADA",
        "PAGADA_PARCIAL",
        "CERRADA",
    ),
    EtapaCiclo.ANULADA: ("ANULADA",),
}


# Tabla 58: los catorce estados de la cuenta.
ESTADOS_CUENTA = frozenset(estado for estados in ESTADOS_POR_ETAPA.values() for estado in estados)
# Tabla 59: los estados del lote.
ESTADOS_LOTE = frozenset(
    {
        "GENERADO",
        "CARGADO_VALIDADOR",
        "OBSERVADO_VALIDADOR",
        "VALIDADO",
        "REMITIDO_IAFAS",
        "ACEPTADO",
        "RECHAZADO",
    }
)
