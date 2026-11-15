"""Carga el catalogo GTIN versionado (Seccion 10, Fase 17): lee
configuracion/reglas_tedef/catalogo_gtin.yaml, crea un registro en
`catalogo_gtin_version` e inserta sus productos. No modifica versiones
anteriores: cada ejecucion agrega una version nueva (mismo patron que
herramientas/cargar_cpms.py, Fase 4).

La trazabilidad de cada producto a su captura y fila de origen (Seccion
3.3: "se registra en docs/DECISIONES.md al cerrar la Fase 17, no en el
archivo de configuracion") vive aqui, no en catalogo_gtin.yaml: este
mapeo es la unica fuente de las columnas `captura`/`fila` de
`catalogo_gtin_producto`, y docs/DECISIONES.md documenta lo mismo en
prosa para quien no vaya a leer este script.

Uso (desde sistema/backend/):
    uv run python herramientas/cargar_catalogo_gtin.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.cargador_catalogo_gtin import (
    RUTA_CATALOGO_GTIN,
    TRAZABILIDAD_CATALOGO_GTIN,
    ErrorCatalogoGtinSinTrazabilidad,
    insertar_version_catalogo_gtin,
    leer_productos_catalogo_gtin,
)

RUTA_CATALOGO = RUTA_CATALOGO_GTIN
_TRAZABILIDAD = TRAZABILIDAD_CATALOGO_GTIN


def _leer_productos() -> list[dict[str, object]]:
    try:
        return leer_productos_catalogo_gtin()
    except ErrorCatalogoGtinSinTrazabilidad as error:
        raise SystemExit(str(error)) from error


async def _cargar(
    productos: list[dict[str, object]],
    fabrica_sesiones: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Devuelve el id de la version creada. `fabrica_sesiones` es
    inyectable para pruebas (por defecto, la sesion real de la app)."""

    fabrica = fabrica_sesiones or FabricaSesiones
    async with fabrica() as sesion:
        version = await insertar_version_catalogo_gtin(sesion, productos)
        await sesion.commit()
        print(f"Version de catalogo GTIN creada (id={version.id}) con {len(productos)} productos.")
        return version.id


def main() -> None:
    productos = _leer_productos()
    print(f"Cargando {len(productos)} productos desde {RUTA_CATALOGO}:")
    asyncio.run(_cargar(productos))


if __name__ == "__main__":
    main()
