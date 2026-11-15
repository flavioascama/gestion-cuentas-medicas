"""Pruebas de autorizacion por ruta de /cuentas/{id}/historial,
/cuentas/{id}/expediente e /indicadores (Seccion 12.2, fila
'Autorizacion'; Fase 29). No prueban el resultado de negocio -- eso ya
lo cubren las pruebas de cada caso de uso -- solo que cada ruta exige
sesion y el rol correcto: el historial y el expediente son exclusivos
del jefe de cuentas medicas (CU-14/CU-16); los indicadores los puede
visualizar tanto el jefe como el gerente administrativo (Tabla 46,
Fase 30: la unica operacion de la matriz con mas de un rol autorizado
fuera de "consultar las cuentas y su detalle")."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_CUERPO_EXPEDIENTE = {"motivo": "auditoria externa"}

# (metodo, ruta, cuerpo) -- solo jefe.
_RUTAS_SOLO_JEFE: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/cuentas/1/historial", None),
    ("POST", "/cuentas/1/expediente", _CUERPO_EXPEDIENTE),
)
# (metodo, ruta, cuerpo) -- jefe o gerente.
_RUTAS_INDICADORES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/indicadores", None),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_trazabilidad_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_trazabilidad_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # ANALISTA opera el ciclo de la cuenta pero no consulta su historial
    # ni exporta su expediente (permiso exclusivo del jefe, Tabla 53).
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_trazabilidad_con_rol_correcto_no_devuelve_401_ni_403(
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


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_INDICADORES)
async def prueba_ruta_indicadores_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_INDICADORES)
async def prueba_ruta_indicadores_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # ANALISTA opera el ciclo de la cuenta pero no visualiza el panel
    # gerencial.
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", [NombreRol.JEFE, NombreRol.GERENTE])
@pytest.mark.parametrize("caso", _RUTAS_INDICADORES)
async def prueba_ruta_indicadores_con_rol_correcto_no_devuelve_401_ni_403(
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
