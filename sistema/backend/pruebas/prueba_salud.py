"""Prueba minima de la Fase 1: el entorno levanta y /salud responde."""

from __future__ import annotations

import httpx

from app.api.main import app


async def prueba_salud_responde_ok() -> None:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        respuesta = await cliente.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
    assert "X-Correlacion-Id" in respuesta.headers
