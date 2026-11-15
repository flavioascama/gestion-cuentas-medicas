"""Evalua el motor de sugerencia CPMS con una consulta corta de "terminos
clave" construida a partir de la denominacion oficial de cada procedimiento
del catalogo vigente, en vez de su denominacion completa (que es lo que
evalua `evaluar_motor_cpms.py`, autorretrieval). No modifica el motor, sus
parametros (configuracion/cpms/motor_sugerencia.yaml) ni ningun otro
componente del sistema: solo lo consulta a traves de su interfaz publica
(`MotorSugerenciaCpms.sugerir`), tal como la consume hoy
`SugerirCodigoCpms` (app/dominio/cpms/casos_uso.py).

Regla de construccion de la consulta (dada por el encargo, no es parte del
motor): denominacion oficial -> minusculas, sin tildes ni puntuacion (se
reusa `normalizar()`, la misma funcion que ya usa el motor para indexar y
para toda consulta) -> se descartan las palabras vacias de la lista dada
-> se toman los dos primeros terminos restantes, en su orden original (o el
unico restante, si solo queda uno).

El motor devuelve como maximo `candidatos_devueltos` (10 en la
configuracion vigente) candidatos por consulta, sin importar que tan alto
se pida `maximo`: por eso, para una consulta en la que el codigo correcto
no aparece entre esos 10, este script NO puede saber en que posicion mas
alla de la 10 habria aparecido -- decirlo exigiria otra configuracion o
reimplementar el ranking por fuera del motor, y el encargo prohibe ambas
cosas. Se deja constancia expresa de esa limitacion en el reporte en vez de
inventar o estimar una posicion.

Uso (desde sistema/backend/):
    uv run python herramientas/evaluar_motor_cpms_terminos_clave.py
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.compartido.rutas import RAIZ_BACKEND, raiz_reportes
from app.dominio.cpms.normalizacion import normalizar
from app.dominio.cpms.puertos import RepositorioCpms
from app.dominio.cpms.valores import FiltrosSugerencia, ProcedimientoCpms
from app.infraestructura.cpms.configuracion_motor import cargar_configuracion_motor
from app.infraestructura.cpms.indice import obtener_motor_vigente
from app.infraestructura.cpms.motor_tfidf import MotorSugerenciaCpmsTfidf
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_cpms_sql import RepositorioCpmsSql

RUTA_INDICE = RAIZ_BACKEND / ".cache" / "motor_cpms" / "indice.joblib"
RUTA_REPORTE = raiz_reportes() / "resultado_prueba_cpms_terminos_clave.md"

_MAXIMO_CANDIDATOS = 10

_PALABRAS_VACIAS = frozenset(
    {
        "de",
        "del",
        "la",
        "las",
        "el",
        "los",
        "y",
        "e",
        "o",
        "u",
        "en",
        "con",
        "por",
        "para",
        "a",
        "al",
        "sin",
        "sobre",
        "un",
        "una",
        "unos",
        "unas",
    }
)


def construir_consulta_terminos_clave(denominacion: str) -> str:
    texto = normalizar(denominacion)
    terminos = [t for t in texto.split() if t not in _PALABRAS_VACIAS]
    if not terminos:
        # Frontera no prevista por la regla: la denominacion completa eran
        # solo palabras vacias. Se usa el primer termino original en vez de
        # una consulta vacia (que el motor no podria puntuar).
        terminos = texto.split()
    return " ".join(terminos[:2])


@dataclass(frozen=True, slots=True)
class _ResultadoConsulta:
    codigo: str
    denominacion: str
    consulta: str
    posicion_encontrada: int | None
    duracion_ms: float


def _consultar(
    motor: MotorSugerenciaCpmsTfidf, procedimiento: ProcedimientoCpms, consulta: str
) -> _ResultadoConsulta:
    inicio = time.monotonic()
    candidatos = motor.sugerir(normalizar(consulta), FiltrosSugerencia(), _MAXIMO_CANDIDATOS)
    duracion_ms = (time.monotonic() - inicio) * 1000
    posiciones = [c.posicion for c in candidatos if c.codigo == procedimiento.codigo]
    return _ResultadoConsulta(
        codigo=procedimiento.codigo,
        denominacion=procedimiento.denominacion,
        consulta=consulta,
        posicion_encontrada=posiciones[0] if posiciones else None,
        duracion_ms=duracion_ms,
    )


def _tabla_resumen(resultados: list[_ResultadoConsulta]) -> dict[str, Any]:
    total = len(resultados)
    en_posicion_1 = sum(1 for r in resultados if r.posicion_encontrada == 1)
    en_top_10 = sum(1 for r in resultados if r.posicion_encontrada is not None)
    duracion_promedio_ms = sum(r.duracion_ms for r in resultados) / total
    return {
        "total": total,
        "en_posicion_1": en_posicion_1,
        "porcentaje_posicion_1": round(100 * en_posicion_1 / total, 2),
        "en_top_10": en_top_10,
        "porcentaje_top_10": round(100 * en_top_10 / total, 2),
        "duracion_promedio_ms": round(duracion_promedio_ms, 4),
    }


async def _evaluar_terminos_clave(
    motor: MotorSugerenciaCpmsTfidf, procedimientos: list[ProcedimientoCpms]
) -> dict[str, Any]:
    resultados = []
    for procedimiento in procedimientos:
        consulta = construir_consulta_terminos_clave(procedimiento.denominacion)
        resultados.append(_consultar(motor, procedimiento, consulta))

    consultas_por_codigo: dict[str, set[str]] = {}
    for resultado in resultados:
        consultas_por_codigo.setdefault(resultado.consulta, set()).add(resultado.codigo)
    consultas_colisionadas = {
        consulta: codigos for consulta, codigos in consultas_por_codigo.items() if len(codigos) > 1
    }

    fallos = [r for r in resultados if r.posicion_encontrada is None]

    return {
        "resumen": _tabla_resumen(resultados),
        "consultas_colisionadas_cantidad": len(consultas_colisionadas),
        "procedimientos_en_consultas_colisionadas": sum(
            len(codigos) for codigos in consultas_colisionadas.values()
        ),
        "ejemplos_colision": [
            {"consulta": consulta, "codigos": sorted(codigos)}
            for consulta, codigos in list(consultas_colisionadas.items())[:5]
        ],
        "fallos_top_10": [
            {
                "codigo": r.codigo,
                "denominacion": r.denominacion,
                "consulta": r.consulta,
            }
            for r in fallos
        ],
        "ejemplos_consulta": [
            {"denominacion": r.denominacion, "consulta": r.consulta} for r in resultados[:8]
        ],
    }


async def _evaluar_autorretrieval(
    motor: MotorSugerenciaCpmsTfidf, procedimientos: list[ProcedimientoCpms]
) -> dict[str, Any]:
    """Repite, en la misma corrida, la prueba de autorretrieval existente
    (herramientas/evaluar_motor_cpms.py): la consulta es la denominacion
    completa normalizada, no la de terminos clave de este script."""

    resultados = []
    for procedimiento in procedimientos:
        resultados.append(_consultar(motor, procedimiento, procedimiento.denominacion))
    return {"resumen": _tabla_resumen(resultados)}


async def main() -> None:
    configuracion_motor = cargar_configuracion_motor()

    async with FabricaSesiones() as sesion:
        repositorio: RepositorioCpms = RepositorioCpmsSql(sesion)
        print("construyendo/cargando el indice del motor...")
        motor = await obtener_motor_vigente(repositorio, RUTA_INDICE, configuracion_motor)
        procedimientos = await repositorio.listar_procedimientos(motor.cpms_version_id)
        print(
            f"version vigente: {motor.cpms_version_etiqueta} ({len(procedimientos)} procedimientos)"
        )

        print("evaluando consultas de terminos clave...")
        resultado_terminos_clave = await _evaluar_terminos_clave(motor, procedimientos)

        print("repitiendo la prueba de autorretrieval existente...")
        resultado_autorretrieval = await _evaluar_autorretrieval(motor, procedimientos)

    reporte = {
        "ejecutado_en": datetime.now().isoformat(timespec="seconds"),
        "version_catalogo_etiqueta": motor.cpms_version_etiqueta,
        "version_catalogo_id": motor.cpms_version_id,
        "total_procedimientos": len(procedimientos),
        "candidatos_devueltos_configurado": configuracion_motor.candidatos_devueltos,
        "terminos_clave": resultado_terminos_clave,
        "autorretrieval": resultado_autorretrieval,
    }
    ruta_json = raiz_reportes() / "evaluacion_motor_cpms_terminos_clave.json"
    ruta_json.parent.mkdir(parents=True, exist_ok=True)
    ruta_json.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    print(f"\ndatos crudos escritos en {ruta_json}")


if __name__ == "__main__":
    asyncio.run(main())
