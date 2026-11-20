"""Pruebas de autorizacion por ruta de /trabajos (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 segun la Seccion 15 del plan v3.
`GET /trabajos/{id}` es solo para analista, jefe y tesoreria (los que
lanzan tareas del robot desde las pantallas): los demas roles no deben
leer el trabajo."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol


async def prueba_obtener_trabajo_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/trabajos/1")
    assert respuesta.status_code == 401


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.JEFE, NombreRol.TESORERIA])
async def prueba_obtener_trabajo_con_rol_permitido_no_devuelve_401_ni_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get("/trabajos/1", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("rol", [NombreRol.AUDITOR, NombreRol.ADMINISTRADOR])
async def prueba_obtener_trabajo_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get("/trabajos/1", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403
