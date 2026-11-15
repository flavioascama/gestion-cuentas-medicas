"""Pruebas de autorizacion por ruta de /trabajos (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 segun la Seccion 15 del plan v3.
`GET /trabajos/{id}` es para cualquier usuario autenticado, sin filtro de
rol -- por eso, a diferencia de las demas rutas de la fase, aqui no hay
una prueba de "rol incorrecto"."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol


async def prueba_obtener_trabajo_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/trabajos/1")
    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.ADMINISTRADOR]
)
async def prueba_obtener_trabajo_con_cualquier_rol_no_devuelve_401(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get("/trabajos/1", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code != 401
