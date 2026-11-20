"""Errores del motor de orquestacion (Seccion 5.2.4 y 6.2.2)."""

from __future__ import annotations


class ErrorTransicionNoDefinida(Exception):
    """RF-08 / Tabla 69 ("secuencia de flujo"): "toda transicion que no
    figure entre las definidas es rechazada". Tambien cubre los dos
    casos de la Tabla 69 que no son una fila faltante del mapa sino una
    regla aparte: ninguna transicion sobre un estado terminal, y
    ANULACION solo desde un estado no terminal."""


class ErrorAnulacionSinAprobacion(Exception):
    """Tabla 69 ("secuencia de flujo"): "la transicion a ANULADA solo se
    admite cuando existe la aprobacion registrada del jefe de cuentas
    medicas" (RF-21). El analista solicita, el jefe aprueba -- el motor
    rechaza la transicion si no hay una aprobacion."""


class ErrorComprobanteDesfasado(Exception):
    """La cuenta corregida ya no factura lo que dice su comprobante: el lote
    y el comprobante diferirian."""

    def __init__(self) -> None:
        super().__init__(
            "El comprobante ya no coincide con la cuenta: emita el comprobante de "
            "reemplazo antes de declarar la corrección."
        )


class ErrorContinuidadEstados(Exception):
    """Tabla 69 ("continuidad"): el estado previo de un evento debe ser el
    estado nuevo del evento anterior del mismo agregado. Se comprueba al
    registrar el evento (verificacion de cumplimiento, 2026-11-12)."""
