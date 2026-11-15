from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.anexo1 import TablaAnexo1, cargar_tablas
from app.datos import IpressPropia, MaestroIafas


def _ruta_docs_fuentes() -> Path:
    """Fuera de Docker (ejecucion local, `uv run pytest` desde
    `simuladores/tedef_web/`), `docs/fuentes` vive cuatro niveles arriba
    de este archivo (`pruebas/` -> `tedef_web/` -> `simuladores/` -> raiz
    del repositorio): `parents[3]`. Dentro de su propio contenedor
    (docker-compose.yml de este simulador monta solo este arbol en
    `/app`, no el repositorio completo) esa cuenta no existe --
    `Path(__file__).resolve().parents[3]` lanza `IndexError` porque
    `/app/pruebas/conftest.py` solo tiene tres antecesores (`/app/pruebas`,
    `/app`, `/`). Ahi se usa `RUTA_DOCS_FUENTES` (la misma variable que ya
    lee `app/configuracion.py`, montada de solo lectura en `/docs_fuentes`
    por el propio docker-compose.yml de este simulador), en vez de volver
    a calcular la ruta con una cuenta de directorios que solo tiene
    sentido para el arbol local completo."""

    desde_entorno = os.environ.get("RUTA_DOCS_FUENTES")
    if desde_entorno:
        return Path(desde_entorno)
    return Path(__file__).resolve().parents[3] / "docs" / "fuentes"


@pytest.fixture(scope="session")
def ruta_docs_fuentes() -> Path:
    return _ruta_docs_fuentes()


@pytest.fixture(scope="session")
def tablas_anexo1(ruta_docs_fuentes: Path) -> dict[str, TablaAnexo1]:
    return cargar_tablas(ruta_docs_fuentes)


@pytest.fixture
def ipress_propia() -> IpressPropia:
    return IpressPropia(
        ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica Pardo S.A.C."
    )


@pytest.fixture
def maestro_iafas() -> tuple[MaestroIafas, ...]:
    return (
        MaestroIafas(codigo="99553", razon_social="IAFAS Uno"),
        MaestroIafas(codigo="96969", razon_social="IAFAS Dos"),
    )
