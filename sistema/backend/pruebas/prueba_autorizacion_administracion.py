"""Pruebas de autorizacion por ruta de /catalogo-gtin (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 extendido en la Fase 19 con
esta ruta nueva."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol


async def prueba_listar_versiones_catalogo_gtin_sin_token_devuelve_401(
    cliente: AsyncClient,
) -> None:
    respuesta = await cliente.get("/catalogo-gtin/versiones")
    assert respuesta.status_code == 401


async def prueba_listar_versiones_catalogo_gtin_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.get(
        "/catalogo-gtin/versiones", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


async def prueba_listar_versiones_catalogo_gtin_con_rol_correcto_devuelve_200(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ADMINISTRADOR)
    respuesta = await cliente.get(
        "/catalogo-gtin/versiones", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == []
