"""Fixtures compartidas: un catalogo sintetico pequeno de asegurados (no
el asegurados.json real de 32 registros, para que las pruebas no dependan
de haber corrido herramientas/generar_datos_sinteticos.py del backend) y
un cliente HTTP contra la app armada con ese catalogo."""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path

# Seccion 8.4: la ruta /admin/captcha/{id} solo responde con
# SIMULADOR_MODO_PRUEBA=true. Tiene que fijarse antes de importar
# app.configuracion (mas abajo, transitivo via app.principal), porque sus
# atributos se leen del entorno una sola vez, al importar el modulo.
os.environ.setdefault("SIMULADOR_MODO_PRUEBA", "true")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.almacenamiento import Almacenamiento  # noqa: E402
from app.datos import RepositorioDatos  # noqa: E402
from app.principal import construir_app  # noqa: E402

_PATRON_CAPTCHA_ID = re.compile(r'name="captcha_id" value="([^"]+)"')

_ASEGURADOS = {
    "metadatos": {"ficticio": True, "semilla": 1, "generado_en": "2026-01-01T00:00:00+00:00"},
    "asegurados": [
        {
            "documento": {"tipo": "1", "numero": "11111111"},
            "nombres": "Ana",
            "apellidos": "Prueba Vigente",
            "iafas_codigo": "00001",
            "escenario": "cobertura_vigente",
            "ficticio": True,
            "estado_afiliacion": "ACTIVO",
            "plan": "PLAN DE PRUEBA",
            "vigente_desde": "2025-01-01",
            "vigente_hasta": "2027-01-01",
        },
        {
            "documento": {"tipo": "1", "numero": "22222222"},
            "nombres": "Beto",
            "apellidos": "Prueba Cancelado",
            "iafas_codigo": "00002",
            "escenario": "cobertura_cancelada",
            "ficticio": True,
            "estado_afiliacion": "CANCELADO",
            "fecha_cancelacion": "2026-01-01",
            "motivo": "Prueba",
        },
        {
            "documento": {"tipo": "1", "numero": "33333333"},
            "nombres": "Cira",
            "apellidos": "Prueba Copago",
            "iafas_codigo": "00001",
            "escenario": "copago_fijo",
            "ficticio": True,
            "estado_afiliacion": "ACTIVO",
            "copago": {"tipo": "fijo", "monto": 25.5},
        },
    ],
}


@pytest_asyncio.fixture
async def repositorio(tmp_path: Path) -> RepositorioDatos:
    ruta = tmp_path / "asegurados.json"
    ruta.write_text(json.dumps(_ASEGURADOS, ensure_ascii=False), encoding="utf-8")
    return RepositorioDatos(ruta)


@pytest_asyncio.fixture
async def almacenamiento(tmp_path: Path) -> Almacenamiento:
    return Almacenamiento(tmp_path / "acredita_salud.sqlite3")


@pytest_asyncio.fixture
async def cliente(
    repositorio: RepositorioDatos, almacenamiento: Almacenamiento
) -> AsyncGenerator[AsyncClient, None]:
    app = construir_app(repositorio, almacenamiento)
    transporte = ASGITransport(app=app)
    async with AsyncClient(
        transport=transporte, base_url="http://prueba", follow_redirects=True
    ) as cliente_http:
        yield cliente_http


async def _resolver_captcha_de(cliente: AsyncClient, pagina_ingreso: str) -> tuple[str, str]:
    """Seccion 8.4: la prueba actua como el usuario humano, leyendo el
    CAPTCHA por la ruta de administracion (SIMULADOR_MODO_PRUEBA=true) en
    vez de resolverlo -- nunca por reconocimiento optico."""

    coincidencia = _PATRON_CAPTCHA_ID.search(pagina_ingreso)
    assert coincidencia is not None, "La pagina de ingreso no trae un captcha_id."
    captcha_id = coincidencia.group(1)
    respuesta_texto = await cliente.get(f"/admin/captcha/{captcha_id}")
    assert respuesta_texto.status_code == 200
    return captcha_id, respuesta_texto.text


@pytest_asyncio.fixture
async def cliente_autenticado(cliente: AsyncClient) -> AsyncClient:
    from app.configuracion import configuracion

    pagina_ingreso = await cliente.get("/ingreso")
    captcha_id, respuesta_captcha = await _resolver_captcha_de(cliente, pagina_ingreso.text)

    respuesta = await cliente.post(
        "/ingreso",
        data={
            "usuario": configuracion.usuario,
            "clave": configuracion.clave,
            "captcha_id": captcha_id,
            "respuesta_captcha": respuesta_captcha,
        },
    )
    assert respuesta.status_code == 200
    return cliente
