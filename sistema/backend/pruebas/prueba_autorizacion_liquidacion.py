"""Pruebas de autorizacion por ruta de /cuentas/{id}/liquidacion y
/cuentas/{id}/pago (Seccion 12.2, fila 'Autorizacion'; Fase 28). No
prueban el resultado de negocio -- eso ya lo cubren las pruebas de cada
caso de uso -- solo que cada ruta exige sesion y el rol correcto
(CU-12: exclusivo de tesoreria, salvo la lectura)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_CUERPO_LIQUIDACION = {"monto_liquidado": "1500.00"}
_CUERPO_PAGO = {"monto_pagado": "1500.00"}

# (metodo, ruta, cuerpo) -- solo tesoreria.
_RUTAS_SOLO_TESORERIA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/cuentas/1/liquidacion", _CUERPO_LIQUIDACION),
    ("POST", "/cuentas/1/pago", _CUERPO_PAGO),
)
# (metodo, ruta, cuerpo) -- analista, auditor, jefe o tesoreria.
_RUTAS_LECTURA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/cuentas/1/liquidacion", None),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_TESORERIA)
async def prueba_ruta_solo_tesoreria_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_TESORERIA)
async def prueba_ruta_solo_tesoreria_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # JEFE lee la liquidacion pero no la registra ni concilia el pago.
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_TESORERIA)
async def prueba_ruta_solo_tesoreria_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await token_para_rol(NombreRol.TESORERIA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_liquidacion_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_liquidacion_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await token_para_rol(NombreRol.ADMINISTRADOR)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA]
)
@pytest.mark.parametrize("caso", _RUTAS_LECTURA)
async def prueba_lectura_de_liquidacion_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    caso: tuple[str, str, dict[str, Any] | None],
    rol: NombreRol,
) -> None:
    metodo, ruta, cuerpo = caso
    token = await token_para_rol(rol)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)
