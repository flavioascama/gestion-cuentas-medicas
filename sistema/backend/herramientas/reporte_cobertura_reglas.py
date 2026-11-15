"""Genera reportes/cobertura_reglas_tedef.md (Seccion 7.4, punto 4).

No exige cubrir el total de criterios extraidos (~458, Seccion 7.4): el
indicador del R1.4 (Seccion 7.7) se cumple con las cinco clases de
criterios sobre los 104 campos de T1, T2 y T3 que este prototipo genera
(obligatoriedad, longitud, tipo de dato, dominio confirmado, suma o
formula declarada explicitamente sobre una sola fila). Las sumas y
formulas que cruzan tablas o filas (Seccion 7.5) son de la Fase 7 y
todavia no tienen estrategia: aparecen aqui como no implementadas, no
como un defecto de esta fase.

Uso (desde sistema/backend/):
    uv run python herramientas/reporte_cobertura_reglas.py
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from app.compartido.rutas import raiz_reportes
from app.dominio.integracion.criterios import CriterioRegla
from app.infraestructura.tedef.carga_criterios import cargar_criterios
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "cobertura_reglas_tedef.md"

# Tablas que este prototipo efectivamente genera (Seccion 1.2).
TABLAS_GENERADAS = {"T1", "T2", "T3"}


def _cobertura_por_tabla(criterios: tuple[CriterioRegla, ...]) -> dict[str, dict[str, int]]:
    por_tabla: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "implementados": 0})
    for criterio in criterios:
        por_tabla[criterio.tabla]["total"] += 1
        if criterio.implementada:
            por_tabla[criterio.tabla]["implementados"] += 1
    return por_tabla


def _lineas_resumen(total: int, implementados: int) -> list[str]:
    return [
        "# Cobertura de reglas de validación TEDEF",
        "",
        f"Total de criterios extraídos del Anexo 1 (las ocho tablas): {total}.",
        f"Implementados con una estrategia registrada: {implementados} "
        f"({implementados / total:.1%}).",
        "",
        "No se exige cubrir el total (Sección 7.4). El indicador del R1.4 (Sección 7.7) "
        "se cumple con cinco clases de criterio sobre los 104 campos de T1, T2 y T3, que "
        "son las únicas tablas que este prototipo genera (Sección 1.2): obligatoriedad, "
        "longitud, tipo de dato, dominio enumerado confirmado, y suma o fórmula declarada "
        "explícitamente **dentro de una misma fila**. Las sumas y fórmulas que cruzan "
        "tablas o filas (Sección 7.5) son consistencia entre tablas y pertenecen a la "
        "Fase 7; aparecen abajo como no implementadas por corresponder a otra fase, no "
        "por ser un defecto de este validador.",
    ]


def _lineas_cobertura_por_tabla(por_tabla: dict[str, dict[str, int]]) -> list[str]:
    lineas = [
        "",
        "## Cobertura por tabla",
        "",
        "| Tabla | Total de criterios | Implementados | Cobertura |",
        "| :---- | ----: | ----: | ----: |",
    ]
    for tabla in sorted(por_tabla):
        datos = por_tabla[tabla]
        cobertura = datos["implementados"] / datos["total"] if datos["total"] else 0.0
        marca = "" if tabla in TABLAS_GENERADAS else " (no se genera)"
        lineas.append(
            f"| {tabla}{marca} | {datos['total']} | {datos['implementados']} | {cobertura:.1%} |"
        )
    return lineas


def _lineas_pendientes_por_campo(criterios: tuple[CriterioRegla, ...]) -> list[str]:
    lineas = [
        "",
        "## Campos de T1, T2 y T3 con criterios sin implementar",
        "",
        "Cuenta de criterios pendientes por campo (no el texto de cada uno, para mantener "
        "el reporte legible). La mayoría corresponde a reglas de negocio específicas de la "
        "IAFAS o a agregaciones entre tablas (Fase 7), no a las cinco clases del indicador.",
        "",
        "| Tabla | Campo | Nombre | Criterios sin implementar |",
        "| :---- | ----: | :---- | ----: |",
    ]
    pendientes_por_campo: dict[tuple[str, int, str], int] = defaultdict(int)
    for criterio in criterios:
        if criterio.tabla in TABLAS_GENERADAS and not criterio.implementada:
            clave = (criterio.tabla, criterio.campo_numero, criterio.campo_nombre)
            pendientes_por_campo[clave] += 1
    for (tabla, campo_numero, campo_nombre), cantidad in sorted(pendientes_por_campo.items()):
        lineas.append(f"| {tabla} | {campo_numero} | {campo_nombre} | {cantidad} |")
    return lineas


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    criterios = cargar_criterios()
    total = len(criterios)
    implementados = sum(1 for c in criterios if c.implementada)

    lineas = cabecera.como_lineas_markdown()
    lineas += _lineas_resumen(total, implementados)
    lineas += _lineas_cobertura_por_tabla(_cobertura_por_tabla(criterios))
    lineas += _lineas_pendientes_por_campo(criterios)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Reporte generado: {SALIDA} ({implementados}/{total} criterios implementados).")


if __name__ == "__main__":
    asyncio.run(main())
