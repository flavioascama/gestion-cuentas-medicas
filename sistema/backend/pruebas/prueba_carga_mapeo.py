"""Integridad del diccionario de mapeo (Seccion 12.1: "verificando que los
104 campos tengan entrada", ampliado a 124 en la Fase 17 con T4) y de los
demas cargadores de configuracion/ que usa el validador."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.infraestructura.tedef.carga_criterios import cargar_criterios
from app.infraestructura.tedef.carga_dominios import cargar_dominios
from app.infraestructura.tedef.carga_esquema import cargar_esquema, version_esquema
from app.infraestructura.tedef.carga_mapeo import (
    RUTA_MAPEO,
    ErrorMapeoIncompleto,
    cargar_mapeo,
    version_mapeo,
)


def prueba_mapeo_cubre_los_124_campos_de_t1_a_t4() -> None:
    mapeo = cargar_mapeo()
    assert len(mapeo) == 124
    for tabla_id, cantidad in (("T1", 31), ("T2", 48), ("T3", 25), ("T4", 20)):
        assert sum(1 for clave in mapeo if clave[0] == tabla_id) == cantidad


def prueba_mapeo_detecta_campo_faltante(tmp_path: Path) -> None:
    with RUTA_MAPEO.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)

    incompleto = [e for e in datos if not (e["tabla"] == "T1" and e["campo"] == 1)]
    ruta_incompleta = tmp_path / "mapeo_incompleto.yaml"
    with ruta_incompleta.open("w", encoding="utf-8") as archivo:
        yaml.safe_dump(incompleto, archivo, allow_unicode=True)

    cargar_mapeo.cache_clear()
    try:
        with pytest.raises(ErrorMapeoIncompleto, match="T1 campo 1"):
            cargar_mapeo(ruta_incompleta)
    finally:
        cargar_mapeo.cache_clear()


def prueba_mapeo_entradas_calculado_o_blanco_tienen_nota() -> None:
    mapeo = cargar_mapeo()
    sin_nota = [
        clave
        for clave, entrada in mapeo.items()
        if entrada.origen in ("calculado", "blanco") and not entrada.nota.strip()
    ]
    assert sin_nota == []


def prueba_esquema_cargado_tiene_8_tablas_y_218_campos() -> None:
    esquema = cargar_esquema()
    assert len(esquema) == 8
    assert sum(len(tabla.campos) for tabla in esquema.values()) == 218


def prueba_criterios_cargados_no_estan_vacios() -> None:
    criterios = cargar_criterios()
    assert len(criterios) > 400
    assert all(c.tabla in {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"} for c in criterios)


def prueba_dominios_cargados_son_todos_no_confirmados() -> None:
    """Ningun script debe marcar un dominio como confirmado (Seccion 7.4):
    esa es una decision humana."""

    dominios = cargar_dominios()
    assert dominios
    assert all(not dominio.confirmado for dominio in dominios.values())


def prueba_versiones_del_esquema_y_del_mapeo_para_el_lote(tmp_path: Path) -> None:
    """RT-06: la version del estandar sale del YAML del esquema y la del
    diccionario de mapeo es la huella de su contenido."""

    assert version_esquema() == "2025-10"
    huella = version_mapeo()
    assert len(huella) == 64
    copia = tmp_path / "mapeo.yaml"
    copia.write_bytes(b"# otro contenido")
    assert version_mapeo(copia) != huella
