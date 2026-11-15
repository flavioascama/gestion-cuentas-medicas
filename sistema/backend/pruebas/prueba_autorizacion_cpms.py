"""Pruebas de autorizacion por ruta de /cpms, /cuentas/{id}/procedimientos
y /catalogo-cpms (Seccion 12.2, fila 'Autorizacion'): entregable de la
Fase 18 segun la Seccion 15 del plan v3. No prueban el resultado de
negocio (eso ya lo cubren las pruebas de cada caso de uso) -- solo que
cada ruta exige sesion y el rol correcto."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient, Response

from app.dominio.acceso.entidades import NombreRol

_CUERPO_CONFIRMAR_PROCEDIMIENTO = {
    "descripcion_registrada": "Consulta ambulatoria",
    "codigo_elegido": "99213",
    "posicion_aceptada": 1,
    "cantidad": 1,
    "monto_unitario": "100.00",
    "fecha": "2026-01-01",
    "inicio_sugerencia": "2026-01-01T00:00:00",
}


async def _pedir(
    cliente: AsyncClient, metodo: str, ruta: str, token: str | None = None
) -> Response:
    encabezados = {"Authorization": f"Bearer {token}"} if token else None
    if ruta == "/cpms/sugerencias":
        return await cliente.request(
            metodo, ruta, params={"descripcion": "dolor abdominal"}, headers=encabezados
        )
    if ruta == "/cuentas/1/procedimientos":
        return await cliente.request(
            metodo, ruta, json=_CUERPO_CONFIRMAR_PROCEDIMIENTO, headers=encabezados
        )
    if metodo == "POST":
        return await cliente.request(metodo, ruta, json={"etiqueta": "prueba"}, headers=encabezados)
    return await cliente.request(metodo, ruta, headers=encabezados)


_RUTAS_SOLO_AUDITOR = (
    ("GET", "/cpms/sugerencias"),
    ("POST", "/cuentas/1/procedimientos"),
)
_RUTAS_SOLO_ADMINISTRADOR = (
    ("GET", "/catalogo-cpms/versiones"),
    ("POST", "/catalogo-cpms/versiones"),
)


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_AUDITOR)
async def prueba_ruta_solo_auditor_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await _pedir(cliente, metodo, ruta)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_AUDITOR)
async def prueba_ruta_solo_auditor_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await _pedir(cliente, metodo, ruta, token)
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_AUDITOR)
async def prueba_ruta_solo_auditor_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.AUDITOR)
    respuesta = await _pedir(cliente, metodo, ruta, token)
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ADMINISTRADOR)
async def prueba_ruta_solo_administrador_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await _pedir(cliente, metodo, ruta)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ADMINISTRADOR)
async def prueba_ruta_solo_administrador_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.AUDITOR)
    respuesta = await _pedir(cliente, metodo, ruta, token)
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta", _RUTAS_SOLO_ADMINISTRADOR)
async def prueba_ruta_solo_administrador_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    token = await token_para_rol(NombreRol.ADMINISTRADOR)
    respuesta = await _pedir(cliente, metodo, ruta, token)
    assert respuesta.status_code not in (401, 403)
