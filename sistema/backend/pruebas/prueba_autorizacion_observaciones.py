"""Pruebas de autorizacion por ruta de /observaciones (Seccion 12.2, fila
'Autorizacion'; Fase 26). No prueban el resultado de negocio (eso ya lo
cubren las pruebas de cada caso de uso) -- solo que cada ruta exige
sesion y el rol correcto segun CU-08 (analista), CU-09 (jefe) y CU-10
(analista o auditor, Tabla 60)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol

_CUERPO_REGISTRO = {"motivo_codigo": "OBS-01", "es_parcial": False}
_CUERPO_RESPUESTA = {"respuesta_texto": "Se adjunta sustento."}

# (metodo, ruta, cuerpo) -- analista, auditor y jefe.
_RUTAS_LECTURA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", "/cuentas/1/observaciones", None),
    ("GET", "/observaciones/motivos", None),
)
# (metodo, ruta, cuerpo) -- solo analista.
_RUTAS_SOLO_ANALISTA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/cuentas/1/observaciones", _CUERPO_REGISTRO),
)
# (metodo, ruta, cuerpo) -- solo jefe.
_RUTAS_SOLO_JEFE: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("PATCH", "/observaciones/1/asignacion", {}),
)
# (metodo, ruta, cuerpo) -- analista o auditor (responsable segun naturaleza).
_RUTAS_RESPONDE: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/observaciones/1/respuesta", _CUERPO_RESPUESTA),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_observaciones_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_observaciones_con_rol_incorrecto_devuelve_403(
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


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE])
@pytest.mark.parametrize("caso", _RUTAS_LECTURA)
async def prueba_lectura_de_observaciones_con_rol_correcto_no_devuelve_401_ni_403(
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


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_observaciones_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_observaciones_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # JEFE lee observaciones pero no registra: confirma que el filtro es
    # "solo analista" y no "cualquier lector".
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_observaciones_con_rol_correcto_no_devuelve_401_ni_403(
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
async def prueba_ruta_solo_jefe_de_observaciones_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_observaciones_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # ANALISTA registra observaciones pero no asigna responsable: confirma
    # que el filtro es "solo jefe" y no "cualquier escritor".
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_JEFE)
async def prueba_ruta_solo_jefe_de_observaciones_con_rol_correcto_no_devuelve_401_ni_403(
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


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_RESPONDE)
async def prueba_ruta_responder_observacion_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_RESPONDE)
async def prueba_ruta_responder_observacion_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # JEFE lee observaciones pero no elabora la respuesta (CU-10 es del
    # responsable, analista o auditor segun la naturaleza, Tabla 60).
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.AUDITOR])
@pytest.mark.parametrize("caso", _RUTAS_RESPONDE)
async def prueba_ruta_responder_observacion_con_rol_correcto_no_devuelve_401_ni_403(
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
