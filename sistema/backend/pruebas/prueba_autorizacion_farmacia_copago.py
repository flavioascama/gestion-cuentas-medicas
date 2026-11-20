"""Autorizacion por ruta (2026-11-19): los productos de farmacia los
registran y quitan el analista y el auditor medico; el cobro del copago lo
registra el analista; el copago del asegurado lo leen los roles que
consultan la cuenta. Solo se prueba el rol, no el resultado de negocio."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_Token = Callable[[NombreRol], Awaitable[str]]

_FARMACIA = (
    ("POST", "/cuentas/1/productos"),
    ("DELETE", "/cuentas/1/productos/1"),
)
_COBRO_COPAGO = (("POST", "/cuentas/1/copago-cobrado"),)
_COPAGO_ASEGURADO = (("GET", "/cuentas/1/copago-asegurado"),)

_CASOS = [
    *[(m, r, NombreRol.ANALISTA, True) for m, r in _FARMACIA],
    *[(m, r, NombreRol.AUDITOR, True) for m, r in _FARMACIA],
    *[(m, r, NombreRol.JEFE, False) for m, r in _FARMACIA],
    *[(m, r, NombreRol.TESORERIA, False) for m, r in _FARMACIA],
    *[(m, r, NombreRol.ADMINISTRADOR, False) for m, r in _FARMACIA],
    *[(m, r, NombreRol.ANALISTA, True) for m, r in _COBRO_COPAGO],
    *[(m, r, NombreRol.AUDITOR, False) for m, r in _COBRO_COPAGO],
    *[(m, r, NombreRol.JEFE, False) for m, r in _COBRO_COPAGO],
    *[(m, r, NombreRol.TESORERIA, False) for m, r in _COBRO_COPAGO],
    *[(m, r, NombreRol.ANALISTA, True) for m, r in _COPAGO_ASEGURADO],
    *[(m, r, NombreRol.AUDITOR, True) for m, r in _COPAGO_ASEGURADO],
    *[(m, r, NombreRol.JEFE, True) for m, r in _COPAGO_ASEGURADO],
    *[(m, r, NombreRol.TESORERIA, True) for m, r in _COPAGO_ASEGURADO],
    *[(m, r, NombreRol.ADMINISTRADOR, False) for m, r in _COPAGO_ASEGURADO],
]


@pytest.mark.parametrize("metodo,ruta", [*_FARMACIA, *_COBRO_COPAGO, *_COPAGO_ASEGURADO])
async def prueba_sin_token_devuelve_401(cliente: AsyncClient, metodo: str, ruta: str) -> None:
    assert (await cliente.request(metodo, ruta)).status_code == 401


@pytest.mark.parametrize("caso", _CASOS)
async def prueba_cada_ruta_exige_su_rol(
    cliente: AsyncClient, token_para_rol: _Token, caso: tuple[str, str, NombreRol, bool]
) -> None:
    metodo, ruta, rol, permitido = caso
    token = await token_para_rol(rol)

    respuesta = await cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})

    if permitido:
        assert respuesta.status_code not in (401, 403)
    else:
        assert respuesta.status_code == 403
