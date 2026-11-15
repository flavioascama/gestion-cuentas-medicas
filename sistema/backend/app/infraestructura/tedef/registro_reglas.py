"""Registro de estrategias por (tabla, campo, criterio) — Seccion 5.2,
patron Registro. Indexa las estrategias parametrizadas que
`configuracion/reglas_tedef/criterios.csv` marca como implementadas.

Aqui se fijan los PARAMETROS de cada estrategia (que campo de referencia,
que campos sumar, que tolerancia): `criterios.csv` solo nombra la familia
en su columna `regla`; los parametros no tienen una columna propia en el
formato de la Seccion 7.4, asi que viven en este modulo, no en el CSV.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from app.dominio.integracion.estrategias import (
    EstrategiaValidacion,
    FechaNoPosteriorA,
    FechaValida,
    HoraValida,
    ProductoConTolerancia,
    RucValido,
    SoloDigitos,
    SumaIgualA,
    ValorEnDominio,
)
from app.infraestructura.tedef.carga_dominios import cargar_dominios

ClaveEstrategia = tuple[str, int, str]  # (tabla, campo_numero, criterio_id)

# Campos con dominio candidato en configuracion/reglas_tedef/dominios.yaml
# cuyo criterio "Solo debe contener uno de los valores definidos" se marco
# como implementada=si en criterios.csv (ver docs/DECISIONES.md, Fase 6).
_CAMPOS_CON_DOMINIO: tuple[ClaveEstrategia, ...] = (
    ("T1", 7, "C1"),
    ("T1", 12, "C1"),
    ("T1", 25, "C1"),
    ("T1", 29, "C1"),
    ("T1", 31, "C1"),
    ("T2", 3, "C1"),
    ("T2", 7, "C1"),
    ("T2", 9, "C1"),
    ("T2", 12, "C1"),
    ("T2", 14, "C1"),
    ("T2", 16, "C1"),
    ("T2", 23, "C1"),
    ("T2", 25, "C1"),
    ("T2", 30, "C1"),
    ("T2", 33, "C1"),
    ("T3", 3, "C1"),
    ("T3", 7, "C1"),
    ("T3", 11, "C1"),
    ("T3", 13, "C1"),
    ("T3", 22, "C1"),
    ("T4", 3, "C1"),
    ("T4", 7, "C1"),
    ("T4", 8, "C1"),
    ("T4", 12, "C1"),
    ("T4", 18, "C1"),
)


@lru_cache
def construir_registro_estrategias() -> dict[ClaveEstrategia, EstrategiaValidacion]:
    """No mutar el diccionario devuelto: esta cacheado por proceso."""

    registro: dict[ClaveEstrategia, EstrategiaValidacion] = {
        ("T1", 3, "C1"): SoloDigitos(),
        ("T1", 11, "C1"): SoloDigitos(),
        ("T2", 5, "C1"): SoloDigitos(),
        ("T3", 6, "C1"): SoloDigitos(),
        ("T3", 15, "C1"): SoloDigitos(),
        ("T3", 24, "C1"): SoloDigitos(),
        ("T4", 6, "C1"): SoloDigitos(),
        # T4 campo 11: decimales=2, no SoloDigitos (docs/DECISIONES.md).
        ("T4", 20, "C1"): SoloDigitos(),
        ("T1", 1, "C1"): FechaValida(),
        ("T1", 9, "C1"): FechaValida(),
        ("T1", 28, "C1"): FechaValida(),
        ("T1", 30, "C1"): FechaValida(),
        ("T2", 21, "C1"): FechaValida(),
        ("T3", 10, "C1"): FechaValida(),
        ("T4", 10, "C1"): FechaValida(),
        ("T1", 2, "C1"): HoraValida(),
        ("T2", 22, "C1"): HoraValida(),
        ("T1", 5, "C1"): RucValido(),
        ("T2", 1, "C1"): RucValido(),
        ("T2", 27, "C1"): RucValido(),
        ("T3", 1, "C1"): RucValido(),
        ("T4", 1, "C1"): RucValido(),
        # T1 campo 9, criterio C2: "la fecha es igual o previa a la fecha
        # de envio" -> compara contra T1 campo 1, de la misma fila.
        ("T1", 9, "C2"): FechaNoPosteriorA(campo_referencia=1),
        # T2 campo 48, criterio C1: suma literal de los campos 35 a 43 de
        # la misma fila (Seccion 7.2, ejemplo del propio plan).
        ("T2", 48, "C1"): SumaIgualA(campos_sumandos=(35, 36, 37, 38, 39, 40, 41, 42, 43)),
        # T3 campo 19, criterio C3: producto de "veces brindado" (campo
        # 15) por "monto unitario" (campo 16), tolerancia +/-0.25.
        ("T3", 19, "C3"): ProductoConTolerancia(campo_a=15, campo_b=16, tolerancia=Decimal("0.25")),
        # T4 campo 15 C4: cantidad (11) x monto unitario (13); sin
        # tolerancia acumulada T3+T4 (docs/DECISIONES.md, Fase 17).
        ("T4", 15, "C4"): ProductoConTolerancia(campo_a=11, campo_b=13, tolerancia=Decimal("0.25")),
    }

    dominios = cargar_dominios()
    for tabla, campo, criterio_id in _CAMPOS_CON_DOMINIO:
        dominio = dominios.get((tabla, campo))
        if dominio is not None:
            registro[(tabla, campo, criterio_id)] = ValorEnDominio(
                dominio.codigos_validos, dominio.confirmado
            )

    return registro
