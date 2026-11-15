"""Pruebas del nombrado de archivos (Seccion 12.1: "Nombrado de archivos y
del .S01, contrastado contra el patron y contra el ejemplo literal del
anexo"). El ejemplo literal es la Seccion 2.2:
937_20100121809_00140456_20002_1234567_201606_20130605.S01"""

from __future__ import annotations

from datetime import date

import pytest

from app.infraestructura.tedef.nombrado import (
    ErrorNombreTedef,
    IdentidadTrama,
    nombre_archivo_s01,
    nombre_archivo_txt,
)

_IDENTIDAD = IdentidadTrama(
    ruc="20100121809",
    codigo_ipress="00140456",
    codigo_iafas="20002",
    numero_lote="1234567",
    periodo="201606",
    fecha=date(2013, 6, 5),
)


def prueba_nombre_txt_calza_con_el_patron() -> None:
    nombre = nombre_archivo_txt("dfac", _IDENTIDAD)
    assert nombre == "dfac_20100121809_00140456_20002_1234567_201606_20130605.txt"


def prueba_nombre_s01_reproduce_el_ejemplo_literal_del_anexo() -> None:
    nombre = nombre_archivo_s01(_IDENTIDAD)
    assert nombre == "937_20100121809_00140456_20002_1234567_201606_20130605.S01"


@pytest.mark.parametrize("prefijo", ["dfac", "date", "dser"])
def prueba_nombre_txt_acepta_los_tres_prefijos_generados(prefijo: str) -> None:
    nombre = nombre_archivo_txt(prefijo, _IDENTIDAD)
    assert nombre.startswith(f"{prefijo}_")


def prueba_ruc_invalido_rechazado() -> None:
    identidad = IdentidadTrama(
        ruc="2010012180",
        codigo_ipress="00140456",
        codigo_iafas="20002",
        numero_lote="1234567",
        periodo="201606",
        fecha=date(2013, 6, 5),
    )
    with pytest.raises(ErrorNombreTedef, match="RUC"):
        nombre_archivo_s01(identidad)


def prueba_numero_de_lote_invalido_rechazado() -> None:
    identidad = IdentidadTrama(
        ruc="20100121809",
        codigo_ipress="00140456",
        codigo_iafas="20002",
        numero_lote="123456",
        periodo="201606",
        fecha=date(2013, 6, 5),
    )
    with pytest.raises(ErrorNombreTedef, match="lote"):
        nombre_archivo_s01(identidad)
