"""Pruebas de los objetos de valor de integracion (Seccion 12.1: 'Validacion
de RUC y de tipo y serie de documento')."""

from __future__ import annotations

import pytest

from app.dominio.integracion.valores import (
    CodigoIafas,
    CodigoIpress,
    Ruc,
    sin_colision_con_padron,
)


def prueba_ruc_valido_de_11_digitos() -> None:
    assert Ruc("20123456789").valor == "20123456789"


@pytest.mark.parametrize(
    "valor",
    ["2012345678", "201234567890", "2012345678a", ""],
    ids=["corto", "largo", "no_numerico", "vacio"],
)
def prueba_ruc_invalido_rechazado(valor: str) -> None:
    with pytest.raises(ValueError, match="RUC invalido"):
        Ruc(valor)


def prueba_codigo_ipress_valido_de_8_caracteres() -> None:
    assert CodigoIpress("12345678").valor == "12345678"


@pytest.mark.parametrize("valor", ["1234567", "123456789", "1234-567"])
def prueba_codigo_ipress_invalido_rechazado(valor: str) -> None:
    with pytest.raises(ValueError, match="Codigo IPRESS invalido"):
        CodigoIpress(valor)


def prueba_codigo_iafas_valido_de_5_digitos() -> None:
    assert CodigoIafas("12345").valor == "12345"


@pytest.mark.parametrize("valor", ["1234", "123456", "1234a"])
def prueba_codigo_iafas_invalido_rechazado(valor: str) -> None:
    with pytest.raises(ValueError, match="Codigo IAFAS invalido"):
        CodigoIafas(valor)


def prueba_sin_colision_sin_padron_disponible_no_rechaza() -> None:
    # Mientras el padron RENIPRESS no este disponible (docs/PENDIENTES.md),
    # no se puede afirmar colision: se deja pasar.
    assert sin_colision_con_padron("12345678", None) is True


def prueba_sin_colision_con_padron_detecta_coincidencia() -> None:
    padron = frozenset({"12345678", "87654321"})
    assert sin_colision_con_padron("12345678", padron) is False
    assert sin_colision_con_padron("00000000", padron) is True
