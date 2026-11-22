"""Motor de orquestacion (R2.4/R2.5, Seccion 5.2.4): funcion pura que
decide si una transicion de la cuenta medica es admisible y, si lo es,
cual es su estado resultante. No ejecuta ninguna actividad del ciclo ni
toca la base de datos -- "el motor no ejecuta las actividades del ciclo
sino que gobierna su secuencia" (Seccion 5.2.4.1): quien llama ya
ejecuto la actividad (o la esta por ejecutar) y solo necesita saber si
el estado que de ahi resulta es un estado que el motor reconoce.

Sin puertos ni efectos secundarios a proposito: es la pieza que la Tabla
69 exige poder verificar con pruebas unitarias simples ("toda
transicion que no figure entre las definidas es rechazada"), sin
levantar Postgres para cada caso.
"""

from __future__ import annotations

from app.dominio.orquestacion.errores import ErrorAnulacionSinAprobacion, ErrorTransicionNoDefinida
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES, TRANSICIONES, TipoTransicion


def validar_transicion(
    estado_actual: str | None,
    transicion: TipoTransicion,
    *,
    aprobacion_anulacion: bool = False,
) -> str:
    """Devuelve el estado resultante si `transicion` esta definida desde
    `estado_actual` en la Tabla 58; si no, levanta
    `ErrorTransicionNoDefinida`. `estado_actual=None` solo es valido
    para `TipoTransicion.REGISTRO` (Tabla 69: "el primer evento de un
    agregado debe ser su registro inicial, cuyo estado previo es
    vacio")."""

    if estado_actual in ESTADOS_TERMINALES:
        raise ErrorTransicionNoDefinida(
            f"La cuenta esta en estado terminal {estado_actual!r}: no admite nuevas transiciones "
            "(Tabla 69, secuencia de flujo)."
        )

    if transicion is TipoTransicion.ANULACION:
        if estado_actual is None:
            raise ErrorTransicionNoDefinida(
                "No se puede anular una cuenta que todavía no se registró."
            )
        if not aprobacion_anulacion:
            raise ErrorAnulacionSinAprobacion(
                "La anulación exige la aprobación registrada del jefe de cuentas médicas."
            )
        return "ANULADA"

    clave = (estado_actual, transicion)
    if clave not in TRANSICIONES:
        raise ErrorTransicionNoDefinida(
            f"La transicion {transicion.value} no esta definida desde el estado "
            f"{estado_actual!r} (Tabla 58)."
        )
    return TRANSICIONES[clave]


def transicion_definida(estado_previo: str | None, estado_nuevo: str) -> bool:
    """Tabla 69 (secuencia), desde el almacen de eventos: si el par
    previo -> nuevo corresponde a alguna transicion de la Tabla 58. ANULADA
    se admite desde cualquier estado no terminal (T-13; la aprobacion ya la
    exige `validar_transicion`)."""

    if estado_nuevo == "ANULADA":
        return estado_previo is not None and estado_previo not in ESTADOS_TERMINALES
    return any(
        previo == estado_previo and nuevo == estado_nuevo
        for (previo, _transicion), nuevo in TRANSICIONES.items()
    )
