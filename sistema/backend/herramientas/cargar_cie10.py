"""Carga el catalogo CIE-10 oficial del MINSA (T2 campo 18, "Primer
Diagnostico"): lee `docs/fuentes/CIE10_MINSA_OFICIAL.xlsx`, crea un
registro en `cie10_version` con huella SHA-256 del archivo e inserta los
codigos. No modifica versiones anteriores: cada ejecucion agrega una
version nueva (mismo patron que `cargar_cpms.py`, Fase 4).

Reemplaza el catalogo provisional de diez codigos de la OMS (Fase 4,
`configuracion/reglas_tedef/cie10_provisional.yaml`, ya eliminado): esos
diez no estaban verificados contra el subconjunto que aprobo el MINSA
(criterio C2 del campo); este archivo es la lista oficial completa.

El catalogo del MINSA trae codigos a tres niveles de anidamiento
(categoria, 3 caracteres; subcategoria, 4; extension propia del MINSA,
5) mas 23 codigos de 6 caracteres. El criterio C3 del campo exige nivel
de subcategoria, y el campo del Anexo 1 mide 5 caracteres: se cargan
solo los codigos de 4 y 5 caracteres, los de 3 y 6 se descartan (Regla 1:
ninguno se trunca ni se inventa para que quepa).

Uso (desde sistema/backend/):
    uv run python herramientas/cargar_cie10.py
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from typing import Any

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compartido.rutas import raiz_docs_fuentes
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo

RUTA_CATALOGO = raiz_docs_fuentes() / "CIE10_MINSA_OFICIAL.xlsx"
_NOMBRE_HOJA = "VOLUMEN VIGENTE"
_LONGITUDES_VALIDAS = (4, 5)  # subcategoria OMS (4) y extension MINSA (5); ver docstring

_PATRON_CODIGO = re.compile(r"^([A-Z]\d{2}[0-9A-Z]{0,3})\s+-\s+(.+)$")


def _leer_codigos() -> list[dict[str, Any]]:
    if not RUTA_CATALOGO.exists():
        sys.exit(f"No se encontro el catalogo CIE-10 en {RUTA_CATALOGO}")
    libro = openpyxl.load_workbook(RUTA_CATALOGO, read_only=True, data_only=True)
    hoja = libro[_NOMBRE_HOJA]
    codigos: dict[str, str] = {}
    for fila in hoja.iter_rows(values_only=True):
        texto = fila[0]
        if not texto:
            continue
        coincidencia = _PATRON_CODIGO.match(texto.strip())
        if coincidencia is None:
            continue
        codigo, descripcion = coincidencia.group(1), coincidencia.group(2).strip()
        if len(codigo) not in _LONGITUDES_VALIDAS:
            continue
        codigos[codigo] = descripcion  # el catalogo no trae duplicados; gana la ultima si hubiera
    return [{"codigo": c, "descripcion": d} for c, d in sorted(codigos.items())]


async def _cargar(
    codigos: list[dict[str, Any]],
    fabrica_sesiones: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Devuelve el id de la version creada. `fabrica_sesiones` es
    inyectable para pruebas (por defecto, la sesion real de la app)."""

    huella = hashlib.sha256(RUTA_CATALOGO.read_bytes()).hexdigest()
    fabrica = fabrica_sesiones or FabricaSesiones
    async with fabrica() as sesion:
        version = Cie10VersionModelo(
            ruta_origen=str(RUTA_CATALOGO), huella_sha256=huella, conteo=len(codigos)
        )
        sesion.add(version)
        await sesion.flush()

        sesion.add_all(Cie10CodigoModelo(cie10_version_id=version.id, **datos) for datos in codigos)
        await sesion.commit()
        print(f"Version de catalogo CIE-10 creada (id={version.id}) con {len(codigos)} codigos.")
        return version.id


def main() -> None:
    codigos = _leer_codigos()
    print(f"Cargando {len(codigos)} codigos desde {RUTA_CATALOGO}:")
    asyncio.run(_cargar(codigos))


if __name__ == "__main__":
    main()
