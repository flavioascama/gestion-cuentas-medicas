"""Pruebas de autorizacion por ruta de /cuentas (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 segun la Seccion 15 del plan v3.
No prueban el resultado de negocio (eso ya lo cubren las pruebas de cada
caso de uso) -- solo que cada ruta exige sesion y el rol correcto.

Tesoreria se agrego a `_RUTAS_LECTURA` en la Fase 30, al consolidar la
matriz de permisos de la Tabla 46 contra las rutas existentes: "consultar
las cuentas y su detalle" la autoriza para los cuatro roles que operan el
ciclo (analista, auditor, jefe, tesoreria), no solo los tres del OE1
original, que no incluia tesoreria porque el rol no existia todavia."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_RUTAS_LECTURA = (
    ("GET", "/cuentas"),
    ("GET", "/cuentas/1"),
)
_RUTAS_SOLO_ANALISTA = (
    ("POST", "/cuentas/1/cobertura"),
    ("GET", "/cuentas/1/acreditacion"),
    ("POST", "/cuentas/asegurado/buscar"),
)


@pytest.mark.parametrize("metodo,ruta", _RUTAS_LECTURA)
async def prueba_lectura_de_cuentas_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta", _RUTAS_LECTURA)
async def prueba_lectura_de_cuentas_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.ADMINISTRADOR)
    respuesta = await cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA]
)
@pytest.mark.parametrize("metodo,ruta", _RUTAS_LECTURA)
async def prueba_lectura_de_cuentas_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    rol: NombreRol,
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cuentas_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cuentas_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.AUDITOR)
    respuesta = await cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cuentas_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(metodo, ruta, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code not in (401, 403)


async def prueba_listar_iafas_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/iafas")
    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.ADMINISTRADOR]
)
async def prueba_listar_iafas_con_cualquier_rol_no_devuelve_401(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get("/iafas", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code != 401
