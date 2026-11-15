"""Genera reportes/evidencia_r13_consultas.csv (Seccion 13 del plan v3 /
Seccion 11 del v2): "por consulta: identificador, instante, duracion,
resultado, intentos" -- indicador R1.3: "menos de 60 segundos por
paciente". La Seccion 13 del v3 agrega una columna: "sesion_vigente
(verdadero en todas las filas validas para el indicador)".

Cada fila conforme de `medicion_paso` con `paso='verificacion_cobertura'`
(Fase 11, `VerificarCobertura._registrar_resultado`) representa, por
construccion, una consulta que tuvo sesion vigente: el robot de
acreditacion (Seccion 8.5, Fase 15) ya no inicia sesion por su cuenta --
si no hubiera sesion activa, el trabajo habria quedado en
`REQUIERE_SESION` y jamas habria llegado a registrar esta medicion. Por
eso `sesion_vigente` es `True` para toda esta tabla, no una columna que
haya que calcular por fila.

Uso (desde sistema/backend/):
    uv run python herramientas/generar_evidencia_r13_consultas.py
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import cast

import sqlalchemy as sa

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import MedicionPasoModelo, TrabajoModelo
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "evidencia_r13_consultas.csv"
_PASO = "verificacion_cobertura"

_ENCABEZADO_COLUMNAS = [
    "cuenta_medica_id",
    "trabajo_id",
    "instante",
    "duracion_ms",
    "menos_de_60s",
    "resultado",
    "intentos",
    "sesion_vigente",
]

_FilaConIntentos = tuple[MedicionPasoModelo, "int | None"]


async def _filas() -> list[_FilaConIntentos]:
    async with FabricaSesiones() as sesion:
        id_trabajo_en_datos = sa.cast(
            MedicionPasoModelo.datos["trabajo_id"].as_string(), sa.Integer
        )
        resultado = await sesion.execute(
            sa.select(MedicionPasoModelo, TrabajoModelo.intentos)
            .where(MedicionPasoModelo.paso == _PASO)
            .outerjoin(TrabajoModelo, TrabajoModelo.id == id_trabajo_en_datos)
            .order_by(MedicionPasoModelo.id)
        )
        # outerjoin puede devolver TrabajoModelo.intentos en None (ningun
        # trabajo con ese id) aunque la columna en si no admita NULL.
        return cast(list[_FilaConIntentos], resultado.all())


def _escribir(ruta: Path, cabecera: list[str], filas: list[_FilaConIntentos]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        for linea in cabecera:
            archivo.write(f"{linea}\n")
        archivo.write("\n")
        escritor = csv.writer(archivo)
        escritor.writerow(_ENCABEZADO_COLUMNAS)
        for medicion, intentos in filas:
            escritor.writerow(
                [
                    medicion.cuenta_medica_id,
                    medicion.datos.get("trabajo_id"),
                    medicion.fin.isoformat(),
                    medicion.duracion_ms,
                    medicion.duracion_ms < 60_000,
                    medicion.resultado,
                    intentos if intentos is not None else 0,
                    True,
                ]
            )


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    filas = await _filas()
    _escribir(SALIDA, cabecera.como_lineas_comentario_csv(), filas)
    print(f"Reporte generado: {SALIDA} ({len(filas)} consultas).")


if __name__ == "__main__":
    asyncio.run(main())
