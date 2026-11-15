"""Pruebas unitarias de la extraccion del esquema TEDEF y del catalogo de
criterios (Seccion 12.1: "Cargador de esquema, incluyendo deteccion de
inconsistencias y recuento de 218 campos"), mas una prueba de regresion
sobre los artefactos ya generados y versionados en configuracion/.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from herramientas.extraer_criterios import _dividir_criterios
from herramientas.extraer_esquema_tedef import (
    SALIDA as ESQUEMA_GENERADO,
)
from herramientas.extraer_esquema_tedef import (
    _obligatorio_de_campo,
    _verificar_invariante_posiciones,
)

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
CRITERIOS_GENERADO = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "criterios.csv"


def _campo(numero: int, longitud: int, posicion_inicial: int) -> dict[str, int]:
    return {"numero": numero, "longitud": longitud, "posicion_inicial": posicion_inicial}


def prueba_invariante_posiciones_correctas_devuelve_longitud_total() -> None:
    campos = [_campo(1, 8, 1), _campo(2, 6, 9), _campo(3, 7, 15)]
    assert _verificar_invariante_posiciones("T1", campos) == 21


def prueba_invariante_detecta_hueco_entre_campos() -> None:
    campos = [_campo(1, 8, 1), _campo(2, 6, 10)]  # deberia empezar en 9, no 10
    with pytest.raises(ValueError, match="posicion_inicial"):
        _verificar_invariante_posiciones("T1", campos)


def prueba_invariante_detecta_numeracion_no_consecutiva() -> None:
    campos = [_campo(1, 8, 1), _campo(3, 6, 9)]  # falta el campo 2
    with pytest.raises(ValueError, match="no consecutiva"):
        _verificar_invariante_posiciones("T1", campos)


def prueba_obligatorio_de_campo_acepta_variantes_de_mayuscula() -> None:
    assert _obligatorio_de_campo("Si") is True
    assert _obligatorio_de_campo("SI") is True
    assert _obligatorio_de_campo("No") is False


def prueba_obligatorio_de_campo_rechaza_valor_desconocido() -> None:
    with pytest.raises(ValueError, match="no reconocido"):
        _obligatorio_de_campo("Tal vez")


def prueba_dividir_criterios_con_marcador_de_punto() -> None:
    texto = "C1. Primer criterio.\nC2. Segundo criterio."
    assert _dividir_criterios(texto) == [
        ("C1", "Primer criterio."),
        ("C2", "Segundo criterio."),
    ]


def prueba_dividir_criterios_con_marcador_de_dos_puntos() -> None:
    texto = "C1: En caso tal, hacer esto."
    assert _dividir_criterios(texto) == [("C1", "En caso tal, hacer esto.")]


def prueba_dividir_criterios_sin_marcador_devuelve_criterio_sintetico_unico() -> None:
    texto = "El campo debe contener valores 'A' o 'D'."
    assert _dividir_criterios(texto) == [("C1", texto)]


def prueba_esquema_generado_tiene_218_campos_en_8_tablas() -> None:
    with ESQUEMA_GENERADO.open(encoding="utf-8") as archivo:
        esquema = yaml.safe_load(archivo)

    assert len(esquema["tablas"]) == 8
    total_campos = sum(len(tabla["campos"]) for tabla in esquema["tablas"])
    assert total_campos == 218

    longitudes_esperadas = {
        "T1": 242,
        "T2": 410,
        "T3": 244,
        "T4": 146,
        "T5": 53,
        "T6": 379,
        "T7": 49,
        "T8": 64,
    }
    for tabla in esquema["tablas"]:
        assert tabla["longitud_registro"] == longitudes_esperadas[tabla["id"]]

    obligatoriedad_esperada = {
        "T1": (True, False),
        "T2": (True, False),
        "T3": (False, True),
        "T4": (False, True),
        "T5": (False, True),
        "T6": (False, False),
        "T7": (False, False),
        "T8": (False, False),
    }
    for tabla in esquema["tablas"]:
        assert (tabla["obligatoria"], tabla["condicional"]) == obligatoriedad_esperada[tabla["id"]]


def prueba_criterios_generados_cubren_los_218_campos() -> None:
    import csv

    with CRITERIOS_GENERADO.open(encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))

    campos_cubiertos = {(fila["tabla"], fila["campo_numero"]) for fila in filas}
    assert len(campos_cubiertos) == 218
    # 'implementada' y 'regla' las edita la Fase 6 a mano (Seccion 7.4,
    # punto 2); esta prueba solo verifica que el valor siga siendo valido,
    # no que nada este implementado todavia.
    assert all(fila["implementada"] in ("si", "no") for fila in filas)
    assert all(fila["regla"] for fila in filas if fila["implementada"] == "si")
