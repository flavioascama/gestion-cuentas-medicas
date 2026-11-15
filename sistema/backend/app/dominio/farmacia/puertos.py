"""Puerto de solo lectura del catalogo GTIN versionado (Seccion 6.1, 10,
Fase 17; listado administrativo Fase 19, Seccion 12, pantalla 8). El
catalogo se sigue cargando con `herramientas/cargar_catalogo_gtin.py`
(sin caso de uso propio, igual que `cargar_cie10.py`) -- este puerto
existe solo para exponer las versiones ya cargadas a la pantalla de
administracion, no para cargarlas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.farmacia.dispensacion import ProductoCatalogo


@dataclass(frozen=True, slots=True)
class VersionCatalogoGtin:
    id: int
    ruta_origen: str
    conteo: int
    cargado_en: datetime


class RepositorioCatalogoGtin(Protocol):
    async def listar_versiones(self) -> list[VersionCatalogoGtin]:
        """Todas las versiones cargadas, mas reciente primero."""
        ...


class CargadorCatalogoGtin(Protocol):
    async def cargar(self) -> VersionCatalogoGtin:
        """Crea una version nueva desde el archivo de configuracion."""
        ...


class RepositorioProductosCatalogoGtin(Protocol):
    async def productos_de_version(self, version_id: int) -> list[ProductoCatalogo]: ...
