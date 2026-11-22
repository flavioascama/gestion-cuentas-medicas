"""El periodo (AAAAMM) como lo lee el usuario: "Octubre-26"."""

from __future__ import annotations

_MESES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Setiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def periodo_legible(periodo: str) -> str:
    """'202610' -> 'Octubre-26'; un valor que no es AAAAMM se devuelve tal cual."""
    if len(periodo) == 6 and periodo.isdigit() and 1 <= int(periodo[4:]) <= 12:
        return f"{_MESES[int(periodo[4:]) - 1]}-{periodo[2:4]}"
    return periodo
