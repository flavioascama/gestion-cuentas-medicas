"""Genera reportes/evidencia_r13_cpms.csv (Seccion 13 del plan v3 /
Seccion 11 del v2, sin cambios entre versiones): "por codificacion:
descripcion, codigo, origen, posicion aceptada, version, verificacion de
existencia" -- indicador: "100% de coincidencia con el catalogo".

Solo las filas de `procedimiento_facturado` con `confirmado_en` no nulo
son "una codificacion" en el sentido del indicador (Seccion 8.2:
confirmacion explicita del auditor, via `ConfirmarCodigoCpms`); las
cargadas por `herramientas/cargar_cuentas_sinteticas.py` como estado de
arranque de las cuentas sinteticas no pasaron por ese flujo.

"Verificacion de existencia" no es una columna propia: `ConfirmarCodigoCpms`
(app/dominio/cpms/casos_uso.py) rechaza con `ErrorCodigoCpmsInexistente`
ANTES de persistir cualquier codigo que no exista en la version vigente
del catalogo (Seccion 8.2: "solo se aceptan codigos existentes") -- que la
fila exista en esta tabla YA es la verificacion positiva.

Uso (desde sistema/backend/):
    uv run python herramientas/generar_evidencia_r13_cpms.py
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
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import ProcedimientoFacturadoModelo
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "evidencia_r13_cpms.csv"

_ENCABEZADO_COLUMNAS = [
    "procedimiento_facturado_id",
    "cuenta_id",
    "descripcion_registrada",
    "codigo_asignado",
    "origen_codigo",
    "posicion_aceptada",
    "version_catalogo",
    "verificacion_existencia",
    "confirmado_en",
]

_FilaCpms = tuple[ProcedimientoFacturadoModelo, str]


async def _filas() -> list[_FilaCpms]:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(ProcedimientoFacturadoModelo, CpmsVersionModelo.etiqueta)
            .join(
                CpmsVersionModelo,
                CpmsVersionModelo.id == ProcedimientoFacturadoModelo.cpms_version_id,
            )
            .where(ProcedimientoFacturadoModelo.confirmado_en.is_not(None))
            .order_by(ProcedimientoFacturadoModelo.id)
        )
        return cast(list[_FilaCpms], resultado.all())


def _escribir(ruta: Path, cabecera: list[str], filas: list[_FilaCpms]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        for linea in cabecera:
            archivo.write(f"{linea}\n")
        archivo.write("\n")
        escritor = csv.writer(archivo)
        escritor.writerow(_ENCABEZADO_COLUMNAS)
        for procedimiento, etiqueta_version in filas:
            escritor.writerow(
                [
                    procedimiento.id,
                    procedimiento.cuenta_id,
                    procedimiento.descripcion_registrada,
                    procedimiento.codigo_asignado,
                    procedimiento.origen_codigo,
                    procedimiento.posicion_aceptada,
                    etiqueta_version,
                    "conforme",
                    procedimiento.confirmado_en.isoformat() if procedimiento.confirmado_en else "",
                ]
            )


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    filas = await _filas()
    _escribir(SALIDA, cabecera.como_lineas_comentario_csv(), filas)
    print(f"Reporte generado: {SALIDA} ({len(filas)} codificaciones confirmadas).")


if __name__ == "__main__":
    asyncio.run(main())
