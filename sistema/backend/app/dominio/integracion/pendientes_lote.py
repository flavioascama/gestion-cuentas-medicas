"""Lo que le falta a una cuenta para entrar a un lote, dicho en palabras
simples (pedido del usuario, 2026-11-18).

El estandar TEDEF habla de tablas, campos y criterios; quien genera el lote
necesita saber de que cuenta se trata y que le falta, para ir a completarlo.
El informe tecnico de la prevalidacion no cambia: esto es una lectura de ese
mismo informe, cuenta por cuenta."""

from __future__ import annotations

from dataclasses import dataclass

from app.dominio.integracion.hallazgos import Hallazgo

FALTA_DIAGNOSTICO = "Falta el diagnóstico principal (CIE-10)."
FALTAN_PROCEDIMIENTOS = "No tiene procedimientos."

# Campos del estandar cuyo problema se explica mejor con el nombre que usa la
# pantalla de la cuenta. Clave: (tabla, numero de campo).
_EXPLICACIONES: dict[tuple[str, int], str] = {
    ("T2", 18): FALTA_DIAGNOSTICO,
}
_MENSAJE_VACIO = "El campo es obligatorio y está vacío."


@dataclass(frozen=True, slots=True)
class PendientesCuenta:
    """Una cuenta que no puede entrar al lote y por que."""

    cuenta_medica_id: int
    identificacion_interna: str
    pendientes: tuple[str, ...]


def pendientes_para_lotear(
    tiene_diagnostico: bool, cantidad_procedimientos: int
) -> tuple[str, ...]:
    """Lo que se puede saber de una cuenta facturada sin armar el lote."""
    pendientes = []
    if not tiene_diagnostico:
        pendientes.append(FALTA_DIAGNOSTICO)
    if cantidad_procedimientos == 0:
        pendientes.append(FALTAN_PROCEDIMIENTOS)
    return tuple(pendientes)


def explicar_hallazgo(hallazgo: Hallazgo) -> str:
    """El problema de un campo, sin tabla, numero de campo ni criterio."""
    conocida = _EXPLICACIONES.get((hallazgo.tabla, hallazgo.campo_numero))
    if conocida is not None:
        return conocida
    if hallazgo.mensaje == _MENSAJE_VACIO:
        return f"Falta: {hallazgo.campo_nombre}."
    return f"{hallazgo.campo_nombre}: {hallazgo.mensaje}"


def explicar_errores(hallazgos: list[Hallazgo]) -> tuple[str, ...]:
    """Una linea por problema distinto, en el orden en que aparecen."""
    errores = (explicar_hallazgo(h) for h in hallazgos if h.severidad == "error")
    return tuple(dict.fromkeys(errores))
