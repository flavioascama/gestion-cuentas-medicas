"""Pruebas de autorizacion por ruta de /cuentas/{id}/cierre,
/cuentas/{id}/anulacion y /anulaciones (Seccion 12.2, fila
'Autorizacion'; Fase 28). No prueban el resultado de negocio -- eso ya
lo cubren las pruebas de cada caso de uso -- solo que cada ruta exige
sesion y el rol correcto segun CU-13: el cierre y la solicitud de
anulacion son del analista; aprobar o rechazar, exclusivo del jefe."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_CUERPO_SOLICITUD_ANULACION = {"motivo": "paciente no se presento"}
_CUERPO_RESOLUCION = {"aprobada": True}

# (metodo, ruta, cuerpo) -- solo analista.
_RUTAS_SOLO_ANALISTA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/cuentas/1/cierre", None),
    ("POST", "/cuentas/1/anulacion/solicitud", _CUERPO_SOLICITUD_ANULACION),
)
# (metodo, ruta, cuerpo) -- solo jefe.
_RUTAS_SOLO_JEFE: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/anulaciones/pendientes", None),
    ("POST", "/anulaciones/1/resolucion", _CUERPO_RESOLUCION),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cierre_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cierre_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # JEFE aprueba o rechaza la anulacion, pero no cierra la cuenta ni
    # la solicita.
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_cierre_con_rol_correcto_no_devuelve_401_ni_403(
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


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_anulaciones_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_anulaciones_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # ANALISTA solicita la anulacion, pero no la aprueba ni la rechaza.
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_anulaciones_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)
