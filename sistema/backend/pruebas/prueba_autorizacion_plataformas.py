"""Pruebas de autorizacion por ruta de /plataformas (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 segun la Seccion 15 del plan v3.
Las cuatro rutas son solo para analista (Seccion 8.4). No prueban el
resultado de negocio (eso ya lo cubren las pruebas de cada caso de uso)
-- solo que cada ruta exige sesion y el rol correcto."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_RUTAS: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/plataformas/sesiones", None),
    ("POST", "/plataformas/essalud/sesion", None),
    ("GET", "/plataformas/sesiones/1/captcha", None),
    ("POST", "/plataformas/sesiones/1/captcha", {"respuesta": "AB12"}),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS)
async def prueba_ruta_de_plataformas_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS)
async def prueba_ruta_de_plataformas_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await token_para_rol(NombreRol.AUDITOR)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS)
async def prueba_ruta_de_plataformas_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)
