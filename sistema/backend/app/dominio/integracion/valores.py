"""Objetos de valor de integracion TEDEF (Seccion 5.2).

Estas clases validan FORMATO (longitud, composicion), no pertenencia a un
registro real. Ningun objeto de esta clase certifica que un valor sea
autentico: los valores que produce `generar_datos_sinteticos.py` son
siempre ficticios (Regla 0.7).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Ruc:
    """11 caracteres numericos (Seccion 2.2). Sin digito verificador: la
    SUNAT no publica el algoritmo de modulo 11 en sus normas de
    comprobantes electronicos (docs/DECISIONES.md, supuesto 4)."""

    valor: str

    def __post_init__(self) -> None:
        if len(self.valor) != 11 or not self.valor.isdigit():
            raise ValueError(f"RUC invalido: {self.valor!r}. Debe ser 11 digitos.")


@dataclass(frozen=True, slots=True)
class CodigoIpress:
    """8 caracteres: numero de registro RENIPRESS vigente (Seccion 2.2).

    Este objeto solo valida longitud y composicion. La comprobacion de que
    el valor NO coincide con un registro RENIPRESS real (Seccion 3.2) es
    responsabilidad de quien genera el valor, con el padron de SUSALUD
    como entrada opcional: ver `sin_colision_con_padron` y
    docs/PENDIENTES.md (padron no disponible todavia)."""

    valor: str

    def __post_init__(self) -> None:
        if len(self.valor) != 8 or not self.valor.isalnum():
            raise ValueError(f"Codigo IPRESS invalido: {self.valor!r}. Debe ser 8 caracteres.")


@dataclass(frozen=True, slots=True)
class CodigoIafas:
    """5 digitos, asignados por SUSALUD (Seccion 2.2)."""

    valor: str

    def __post_init__(self) -> None:
        if len(self.valor) != 5 or not self.valor.isdigit():
            raise ValueError(f"Codigo IAFAS invalido: {self.valor!r}. Debe ser 5 digitos.")


@dataclass(frozen=True, slots=True)
class NumeroLote:
    """7 digitos, asignado transaccionalmente y unico por IAFAS (Seccion 7.6)."""

    valor: str

    def __post_init__(self) -> None:
        if len(self.valor) != 7 or not self.valor.isdigit():
            raise ValueError(f"Numero de lote invalido: {self.valor!r}. Debe ser 7 digitos.")


@dataclass(frozen=True, slots=True)
class Periodo:
    """6 digitos AAAAMM (Decision de la Fase 1, supuesto 5: el anexo define
    el significado del campo pero no su formato; se adopta el del ejemplo
    literal del Anexo 3)."""

    valor: str

    def __post_init__(self) -> None:
        if len(self.valor) != 6 or not self.valor.isdigit():
            raise ValueError(f"Periodo invalido: {self.valor!r}. Debe ser AAAAMM.")
        mes = int(self.valor[4:6])
        if not (1 <= mes <= 12):
            raise ValueError(f"Periodo invalido: {self.valor!r}. Mes fuera de rango.")


@dataclass(frozen=True, slots=True)
class MontoTedef:
    """Monto con 2 decimales, nunca negativo (Seccion 7.3)."""

    valor: Decimal

    def __post_init__(self) -> None:
        if self.valor < 0:
            raise ValueError(f"Monto TEDEF invalido: {self.valor}. No puede ser negativo.")
        if self.valor.as_tuple().exponent != -2:
            raise ValueError(f"Monto TEDEF invalido: {self.valor}. Debe tener 2 decimales.")


def sin_colision_con_padron(codigo: str, codigos_padron: frozenset[str] | None) -> bool:
    """True si `codigo` no aparece en el padron real, o si el padron no
    esta disponible (caso en que no se puede afirmar nada: ver
    docs/PENDIENTES.md, RENIPRESS). El llamador decide si advertir."""

    if codigos_padron is None:
        return True
    return codigo not in codigos_padron
