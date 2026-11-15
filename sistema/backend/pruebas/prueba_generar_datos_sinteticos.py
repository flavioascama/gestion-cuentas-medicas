"""Pruebas del generador de datos sinteticos (Seccion 3.3): determinismo,
cobertura de los 8 escenarios y tamanos de lote. No llama a `main()`: eso
escribiria sobre los fixtures reales versionados en Git."""

from __future__ import annotations

import random
from dataclasses import asdict

from faker import Faker

from herramientas.escenarios_productos_farmacia import _LETRAS_PRODUCTO_DEMO
from herramientas.generar_datos_sinteticos import (
    _TAMANOS_LOTE,
    ESCENARIOS,
    SEMILLA,
    _generar_asegurados,
    _generar_claves_iafas,
    _generar_cuentas_medicas,
    _generar_maestro_iafas,
    _generar_maestro_ipress,
)


def _faker_reiniciado() -> Faker:
    random.seed(SEMILLA)
    Faker.seed(SEMILLA)
    return Faker("es_ES")


def prueba_maestro_iafas_tiene_entre_3_y_5_filas_y_codigos_unicos() -> None:
    filas = _generar_maestro_iafas(_faker_reiniciado())
    assert 3 <= len(filas) <= 5
    assert len({fila.codigo for fila in filas}) == len(filas)
    assert all(fila.ficticio for fila in filas)


def prueba_maestro_ipress_tiene_entre_3_y_5_filas_con_ruc_y_codigo_validos() -> None:
    filas = _generar_maestro_ipress(_faker_reiniciado())
    assert 3 <= len(filas) <= 5
    assert all(len(fila.ruc) == 11 and fila.ruc.isdigit() for fila in filas)
    assert all(len(fila.codigo_ipress) == 8 for fila in filas)
    assert len({fila.codigo_ipress for fila in filas}) == len(filas)


def prueba_generacion_es_determinista_con_la_misma_semilla() -> None:
    primera = _generar_maestro_iafas(_faker_reiniciado())
    segunda = _generar_maestro_iafas(_faker_reiniciado())
    assert [asdict(f) for f in primera] == [asdict(f) for f in segunda]


def prueba_asegurados_cubre_los_8_escenarios_con_al_menos_30_en_total() -> None:
    faker = _faker_reiniciado()
    iafas = _generar_maestro_iafas(faker)
    ipress = _generar_maestro_ipress(faker)
    codigos_iafas = [f.codigo for f in iafas]
    codigos_ipress = [f.codigo_ipress for f in ipress]

    asegurados = _generar_asegurados(faker, codigos_iafas, codigos_ipress)

    assert len(asegurados) >= 30
    escenarios_presentes = {asegurado["escenario"] for asegurado in asegurados}
    assert escenarios_presentes == set(ESCENARIOS)
    for escenario in ESCENARIOS:
        assert sum(1 for a in asegurados if a["escenario"] == escenario) >= 1
    assert all(asegurado["ficticio"] is True for asegurado in asegurados)

    documentos = [(a["documento"]["tipo"], a["documento"]["numero"]) for a in asegurados]
    assert len(set(documentos)) == len(documentos)  # sin duplicados


def prueba_claves_iafas_tiene_una_contrasena_no_vacia_por_cada_iafas() -> None:
    faker = _faker_reiniciado()
    iafas = _generar_maestro_iafas(faker)

    claves = _generar_claves_iafas(iafas, faker)

    assert set(claves) == {fila.codigo for fila in iafas}
    assert all(len(clave) >= 8 for clave in claves.values())


def prueba_diagnostico_en_carencia_queda_marcado_como_pendiente() -> None:
    faker = _faker_reiniciado()
    iafas = _generar_maestro_iafas(faker)
    ipress = _generar_maestro_ipress(faker)
    asegurados = _generar_asegurados(
        faker, [f.codigo for f in iafas], [f.codigo_ipress for f in ipress]
    )

    en_carencia = [a for a in asegurados if a["escenario"] == "diagnostico_en_carencia"]
    assert en_carencia
    for asegurado in en_carencia:
        assert asegurado["diagnostico_en_carencia"]["codigo_cie10"] is None


def prueba_cuentas_medicas_respeta_los_tamanos_de_lote_y_usa_codigos_cpms_reales() -> None:
    faker = _faker_reiniciado()
    iafas = _generar_maestro_iafas(faker)
    ipress = _generar_maestro_ipress(faker)
    asegurados = _generar_asegurados(
        faker, [f.codigo for f in iafas], [f.codigo_ipress for f in ipress]
    )

    lotes = _generar_cuentas_medicas(asegurados, ipress[0].codigo_ipress, faker)

    assert set(lotes.keys()) == set(_TAMANOS_LOTE.keys())
    for nombre_lote, tamano_esperado in _TAMANOS_LOTE.items():
        assert len(lotes[nombre_lote]) == tamano_esperado

    for cuenta in lotes["pequeno"]:
        assert cuenta["ficticio"] is True
        assert cuenta["ipress_codigo"] == ipress[0].codigo_ipress
        assert 1 <= len(cuenta["procedimientos"]) <= 4
        for procedimiento in cuenta["procedimientos"]:
            assert procedimiento["codigo_cpms"]
            assert procedimiento["denominacion"]
            assert procedimiento["monto_unitario"] > 0


def prueba_cuentas_con_productos_cubren_las_letras_del_catalogo_y_un_no_cubierto() -> None:
    faker = _faker_reiniciado()
    iafas = _generar_maestro_iafas(faker)
    ipress = _generar_maestro_ipress(faker)
    asegurados = _generar_asegurados(
        faker, [f.codigo for f in iafas], [f.codigo_ipress for f in ipress]
    )

    lotes = _generar_cuentas_medicas(asegurados, ipress[0].codigo_ipress, faker)

    todas_las_cuentas = [c for cuentas in lotes.values() for c in cuentas]
    cuentas_con_productos = [c for c in todas_las_cuentas if c.get("productos")]
    assert len(cuentas_con_productos) == len(_LETRAS_PRODUCTO_DEMO)

    letras_presentes = {
        producto["tipo_producto"]
        for cuenta in cuentas_con_productos
        for producto in cuenta["productos"]
    }
    assert letras_presentes == set(_LETRAS_PRODUCTO_DEMO)

    productos = [p for c in cuentas_con_productos for p in c["productos"]]
    assert any(p["monto_no_cubierto"] > 0 for p in productos)
    assert all(p["catalogo"] == "1" and p["codigo_producto"] for p in productos)
