"""Pruebas de las funciones puras de parseo del robot de acreditacion
(Seccion 8.1): convertir el texto que muestra el simulador ('S/ 53.99',
'20%') a los tipos que espera ResultadoAcreditacion."""

from __future__ import annotations

from decimal import Decimal

from trabajador.robots.robot_acreditacion import _decimal_opcional, _entero_opcional


def prueba_decimal_opcional_quita_el_prefijo_de_moneda() -> None:
    assert _decimal_opcional("S/ 53.99") == Decimal("53.99")


def prueba_decimal_opcional_con_none_devuelve_none() -> None:
    assert _decimal_opcional(None) is None


def prueba_decimal_opcional_con_texto_invalido_devuelve_none() -> None:
    assert _decimal_opcional("no es un monto") is None


def prueba_entero_opcional_quita_el_simbolo_de_porcentaje() -> None:
    assert _entero_opcional("20%") == 20


def prueba_entero_opcional_con_none_devuelve_none() -> None:
    assert _entero_opcional(None) is None


def prueba_entero_opcional_con_texto_invalido_devuelve_none() -> None:
    assert _entero_opcional("no es un porcentaje") is None
