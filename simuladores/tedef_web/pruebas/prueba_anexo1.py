from __future__ import annotations

from app.anexo1 import TablaAnexo1

_LONGITUDES_ESPERADAS = {"T1": 242, "T2": 410, "T3": 244, "T4": 146}


def prueba_carga_las_cuatro_tablas_activas(tablas_anexo1: dict[str, TablaAnexo1]) -> None:
    assert set(tablas_anexo1) == {"T1", "T2", "T3", "T4"}


def prueba_suma_de_longitudes_de_campo_coincide_con_el_registro(
    tablas_anexo1: dict[str, TablaAnexo1],
) -> None:
    for tabla_id, tabla in tablas_anexo1.items():
        assert sum(campo.longitud for campo in tabla.campos) == _LONGITUDES_ESPERADAS[tabla_id]
        assert tabla.longitud_registro == _LONGITUDES_ESPERADAS[tabla_id]


def prueba_numeracion_de_campos_es_consecutiva(tablas_anexo1: dict[str, TablaAnexo1]) -> None:
    for tabla in tablas_anexo1.values():
        numeros = [campo.numero for campo in tabla.campos]
        assert numeros == list(range(1, len(numeros) + 1))


def prueba_posiciones_encajan_una_tras_otra(tablas_anexo1: dict[str, TablaAnexo1]) -> None:
    for tabla in tablas_anexo1.values():
        posicion_esperada = 1
        for campo in tabla.campos:
            assert campo.posicion_inicial == posicion_esperada
            posicion_esperada += campo.longitud
