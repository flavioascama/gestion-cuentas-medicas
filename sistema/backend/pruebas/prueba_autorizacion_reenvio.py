"""Pruebas de autorizacion de /cuentas/{id}/rechazo y
/cuentas/{id}/correccion-reenvio (T-05): leer el rechazo es de los cuatro
roles que leen la cuenta; corregir para el reenvio, solo del analista."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_CUERPO_CORRECCION = {"descripcion_correccion": "se corrigio la serie del comprobante"}


async def prueba_correccion_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.post("/cuentas/1/correccion-reenvio", json=_CUERPO_CORRECCION)
    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "rol", [NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA, NombreRol.GERENTE]
)
async def prueba_correccion_con_rol_distinto_de_analista_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    rol: NombreRol,
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.post(
        "/cuentas/1/correccion-reenvio",
        json=_CUERPO_CORRECCION,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 403


async def prueba_correccion_con_analista_no_devuelve_401_ni_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.post(
        "/cuentas/1/correccion-reenvio",
        json=_CUERPO_CORRECCION,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize(
    "rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA]
)
async def prueba_rechazo_lo_leen_los_roles_de_consulta_de_cuentas(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    rol: NombreRol,
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get(
        "/cuentas/1/rechazo", headers={"Authorization": f"Bearer {token}"}
    )
    # La cuenta 1 no existe en la base vacia de la prueba: 404, no 401/403.
    assert respuesta.status_code == 404


async def prueba_rechazo_no_lo_lee_el_gerente(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.GERENTE)
    respuesta = await cliente.get(
        "/cuentas/1/rechazo", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403
