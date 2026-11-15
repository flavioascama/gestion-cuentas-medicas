"""Genera reportes/evidencia_mediciones_pasos.csv (Seccion 13 del plan
v3 / Seccion 11 del v2, sin cambios entre versiones): "una fila por
ejecucion de paso: paso, identificador de cuenta o lote, inicio, fin,
duracion del sistema, duracion total con confirmacion humana, resultado".

La separacion "duracion del sistema" / "duracion total con confirmacion
humana" ya esta modelada en `medicion_paso` desde la Fase 9 (Seccion 6.4):
son dos FILAS con `paso` distinto para el mismo evento de codificacion
(`codificacion_sistema` y `codificacion_total`), nunca dos columnas en la
misma fila -- por eso esta herramienta vuelca la tabla tal cual, sin
recalcular nada.

Uso (desde sistema/backend/):
    uv run python herramientas/generar_evidencia_mediciones_pasos.py
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

import sqlalchemy as sa

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import MedicionPasoModelo
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "evidencia_mediciones_pasos.csv"

_ENCABEZADO_COLUMNAS = [
    "id",
    "paso",
    "cuenta_medica_id",
    "lote_id",
    "inicio",
    "fin",
    "duracion_ms",
    "actor",
    "resultado",
]


async def _filas() -> list[MedicionPasoModelo]:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(MedicionPasoModelo).order_by(MedicionPasoModelo.id)
        )
        return list(resultado.scalars())


def _escribir(ruta: Path, cabecera: list[str], filas: list[MedicionPasoModelo]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        for linea in cabecera:
            archivo.write(f"{linea}\n")
        archivo.write("\n")
        escritor = csv.writer(archivo)
        escritor.writerow(_ENCABEZADO_COLUMNAS)
        for medicion in filas:
            escritor.writerow(
                [
                    medicion.id,
                    medicion.paso,
                    medicion.cuenta_medica_id,
                    medicion.lote_id,
                    medicion.inicio.isoformat(),
                    medicion.fin.isoformat(),
                    medicion.duracion_ms,
                    medicion.actor,
                    medicion.resultado,
                ]
            )


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    filas = await _filas()
    _escribir(SALIDA, cabecera.como_lineas_comentario_csv(), filas)
    print(f"Reporte generado: {SALIDA} ({len(filas)} mediciones).")


if __name__ == "__main__":
    asyncio.run(main())
