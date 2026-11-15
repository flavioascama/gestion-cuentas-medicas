"""Carga el catalogo CPMS versionado (Seccion 8.2): lee una o varias
'Parte_N_...xlsx', crea un registro en `cpms_version` con etiqueta,
archivos de origen, huella SHA-256 de cada uno y conteo, e inserta los
procedimientos. No modifica versiones anteriores: cada ejecucion agrega
una version nueva.

Uso (desde sistema/backend/):
    uv run python herramientas/cargar_cpms.py
    uv run python herramientas/cargar_cpms.py --etiqueta 2023-06-05 \
        ../../docs/fuentes/Parte_1_050623_..._ok15.xlsx

Sin archivos posicionales, se descubren automaticamente todas las
'Parte_*.xlsx' en docs/fuentes/. Sin --etiqueta, se usa la fecha de hoy.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compartido.rutas import raiz_docs_fuentes
from app.infraestructura.cpms.lector_catalogo_cpms import descubrir_partes, leer_procedimientos
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_cpms import (
    CpmsProcedimientoModelo,
    CpmsVersionModelo,
)

CARPETA_FUENTES = raiz_docs_fuentes()

# Alias locales: el resto de este script (y sus pruebas) ya usaba estos
# nombres antes de que la Fase 18 extrajera la lectura a
# app/infraestructura/cpms/lector_catalogo_cpms.py, compartida con
# CargarCatalogoCpms (`POST /catalogo-cpms/versiones`).
_leer_procedimientos = leer_procedimientos


def _descubrir_partes() -> list[Path]:
    partes = descubrir_partes()
    if not partes:
        sys.exit(f"No se hallaron archivos 'Parte_*.xlsx' en {CARPETA_FUENTES}")
    return partes


async def _cargar(
    rutas: list[Path],
    etiqueta: str,
    fabrica_sesiones: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Devuelve el id de la version creada. `fabrica_sesiones` es
    inyectable para pruebas (por defecto, la sesion real de la app)."""

    todos_los_procedimientos: list[dict[str, Any]] = []
    archivos_origen: list[dict[str, str]] = []
    for ruta in rutas:
        procedimientos = _leer_procedimientos(ruta)
        huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
        archivos_origen.append({"archivo": ruta.name, "huella_sha256": huella})
        todos_los_procedimientos.extend(procedimientos)
        print(f"  {ruta.name}: {len(procedimientos)} procedimientos, huella {huella[:12]}...")

    fabrica = fabrica_sesiones or FabricaSesiones
    async with fabrica() as sesion:
        version = CpmsVersionModelo(
            etiqueta=etiqueta,
            archivos_origen=archivos_origen,
            conteo=len(todos_los_procedimientos),
        )
        sesion.add(version)
        await sesion.flush()  # asigna version.id sin cerrar la transaccion

        sesion.add_all(
            CpmsProcedimientoModelo(cpms_version_id=version.id, **datos)
            for datos in todos_los_procedimientos
        )
        await sesion.commit()
        print(
            f"Version CPMS '{etiqueta}' creada (id={version.id}) con "
            f"{len(todos_los_procedimientos)} procedimientos."
        )
        return version.id


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "archivos", nargs="*", type=Path, help="rutas a los archivos 'Parte_N_...xlsx'"
    )
    analizador.add_argument(
        "--etiqueta",
        default=date.today().isoformat(),
        help="etiqueta de la version (por defecto: fecha de hoy)",
    )
    argumentos = analizador.parse_args()

    rutas = argumentos.archivos or _descubrir_partes()
    for ruta in rutas:
        if not ruta.exists():
            sys.exit(f"No se encontro el archivo: {ruta}")

    print(f"Cargando {len(rutas)} archivo(s) como version '{argumentos.etiqueta}':")
    asyncio.run(_cargar(rutas, argumentos.etiqueta))


if __name__ == "__main__":
    main()
