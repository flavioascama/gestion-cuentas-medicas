"""Validador de campo (Seccion 7.4, 7.6, 7.7): valida UN registro (una
fila de una tabla) a la vez.

Aplica, para cada uno de sus campos: (a) las verificaciones estructurales
de obligatoriedad y longitud, siempre, tomadas del esquema (Seccion 7.7,
punto 5); (b) la de monto con 2 decimales, cuando el esquema declara
decimales=2; y (c) las estrategias de `registro_reglas` para cada
criterio de `criterios.csv` marcado como implementada=si.

No agrega entre filas ni entre tablas: eso es consistencia entre tablas
(Seccion 7.5) y pertenece a la Fase 7, que sí tiene el registro completo
del lote para comparar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.dominio.integracion.criterios import CriterioRegla
from app.dominio.integracion.esquema import CampoEsquema, TablaEsquema
from app.dominio.integracion.estrategias import (
    EstrategiaValidacion,
    LongitudExacta,
    MontoDosDecimales,
    ObligatorioNoVacio,
)
from app.dominio.integracion.hallazgos import Hallazgo
from app.infraestructura.tedef.carga_criterios import cargar_criterios
from app.infraestructura.tedef.registro_reglas import (
    ClaveEstrategia,
    construir_registro_estrategias,
)

_ESTRUCTURAL_OBLIGATORIO = ObligatorioNoVacio()
_ESTRUCTURAL_LONGITUD = LongitudExacta()
_ESTRUCTURAL_MONTO = MontoDosDecimales()

# La columna "Obligatorio" del Anexo 1 es una marca de base: no distingue
# los campos cuya obligatoriedad depende de OTRO campo, ni los que su
# propia definicion admite blanco. Detectado al verificar esta fase contra
# datos reales (docs/DECISIONES.md): estos campos quedan exentos de la
# verificacion ESTRUCTURAL de obligatoriedad porque su propio criterio (no
# el flag "Obligatorio" en bruto) ya lo permite:
#   - T2 25/26 y T3 13/14: en blanco cuando el Tipo del Profesional
#     Responsable (T2 23 / T3 11) es '00' (criterio C2/C4 de esos campos).
#   - T3 21 (Diagnostico Asociado): su propia definicion admite blanco
#     ("De no tenerse se consignara... o en blanco").
_EXENTOS_DE_OBLIGATORIEDAD_ESTRUCTURAL: frozenset[tuple[str, int]] = frozenset(
    {("T2", 25), ("T2", 26), ("T3", 13), ("T3", 14), ("T3", 21)}
)


def _criterio_estructural(
    tabla: str, campo_numero: int, campo_nombre: str, texto: str, regla: str
) -> CriterioRegla:
    return CriterioRegla(
        tabla=tabla,
        campo_numero=campo_numero,
        campo_nombre=campo_nombre,
        criterio_id="ESTRUCTURAL",
        texto_literal=texto,
        implementada=True,
        regla=regla,
    )


@dataclass(frozen=True, slots=True)
class _ContextoCampo:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    toda verificacion de un campo necesita, para no superar el limite de 5
    parametros por funcion (Seccion 3)."""

    tabla: TablaEsquema
    campo: CampoEsquema
    valor: str
    registro: Mapping[int, str]


def _evaluar_estructural(
    contexto: _ContextoCampo, estrategia: EstrategiaValidacion, texto: str, regla: str
) -> list[Hallazgo]:
    criterio = _criterio_estructural(
        contexto.tabla.id, contexto.campo.numero, contexto.campo.nombre, texto, regla
    )
    hallazgo = estrategia.evaluar(
        tabla=contexto.tabla.id,
        campo=contexto.campo,
        valor=contexto.valor,
        registro=contexto.registro,
        criterio=criterio,
    )
    return [hallazgo] if hallazgo else []


def _validar_estructurales(contexto: _ContextoCampo) -> list[Hallazgo]:
    """Obligatoriedad (salvo exento), longitud y, si aplica, formato de
    monto -- las tres verificaciones que valen para todo campo, tomadas
    directamente del esquema (Seccion 7.7, punto 5)."""

    hallazgos: list[Hallazgo] = []
    if (contexto.tabla.id, contexto.campo.numero) not in _EXENTOS_DE_OBLIGATORIEDAD_ESTRUCTURAL:
        hallazgos.extend(
            _evaluar_estructural(
                contexto,
                _ESTRUCTURAL_OBLIGATORIO,
                "Obligatoriedad declarada en el esquema (Seccion 7.1).",
                "obligatorio_no_vacio",
            )
        )

    hallazgos.extend(
        _evaluar_estructural(
            contexto,
            _ESTRUCTURAL_LONGITUD,
            "Longitud declarada en el esquema (Seccion 7.1).",
            "longitud_exacta",
        )
    )

    if contexto.campo.decimales == 2:
        hallazgos.extend(
            _evaluar_estructural(
                contexto,
                _ESTRUCTURAL_MONTO,
                "Formato de monto con 2 decimales, sin negativos (Seccion 7.3).",
                "monto_dos_decimales",
            )
        )

    return hallazgos


def _validar_criterios_adicionales(
    contexto: _ContextoCampo,
    criterios_del_campo: list[CriterioRegla],
    registro_estrategias: Mapping[ClaveEstrategia, EstrategiaValidacion],
) -> list[Hallazgo]:
    """Estrategias de `registro_reglas` para cada criterio de
    `criterios.csv` marcado como implementada=si (Seccion 7.4)."""

    tabla, campo, valor, registro = (
        contexto.tabla,
        contexto.campo,
        contexto.valor,
        contexto.registro,
    )
    hallazgos: list[Hallazgo] = []
    for criterio in criterios_del_campo:
        if not criterio.implementada:
            continue
        estrategia = registro_estrategias.get((tabla.id, campo.numero, criterio.criterio_id))
        if estrategia is None:
            continue
        hallazgo = estrategia.evaluar(
            tabla=tabla.id, campo=campo, valor=valor, registro=registro, criterio=criterio
        )
        if hallazgo:
            hallazgos.append(hallazgo)
    return hallazgos


def validar_registro(tabla: TablaEsquema, registro: Mapping[int, str]) -> list[Hallazgo]:
    """`registro`: texto de cada campo de esta fila, indexado por numero de
    campo, tal como quedaria en el archivo de ancho fijo."""

    criterios_por_campo: dict[int, list[CriterioRegla]] = {}
    for criterio in cargar_criterios():
        if criterio.tabla == tabla.id:
            criterios_por_campo.setdefault(criterio.campo_numero, []).append(criterio)

    registro_estrategias = construir_registro_estrategias()

    hallazgos: list[Hallazgo] = []
    for campo in tabla.campos:
        contexto = _ContextoCampo(
            tabla=tabla, campo=campo, valor=registro.get(campo.numero, ""), registro=registro
        )
        hallazgos.extend(_validar_estructurales(contexto))
        hallazgos.extend(
            _validar_criterios_adicionales(
                contexto, criterios_por_campo.get(campo.numero, []), registro_estrategias
            )
        )
    return hallazgos
