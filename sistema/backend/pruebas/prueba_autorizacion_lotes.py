"""Pruebas de autorizacion por ruta de /lotes (Seccion 12.2, fila
'Autorizacion'): entregable de la Fase 18 segun la Seccion 15 del plan v3.
No prueban el resultado de negocio (eso ya lo cubren las pruebas de cada
caso de uso) -- solo que cada ruta exige sesion y el rol correcto."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import EventoModelo

_CUERPO_GENERAR_LOTE = {"iafas_id": 1, "periodo": "2026-01", "cuenta_ids": []}
_CUERPO_ENVIO_SUSALUD = {"periodo": "2026-01"}

# (metodo, ruta, cuerpo) -- analista y jefe.
_RUTAS_LECTURA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/lotes", _CUERPO_GENERAR_LOTE),
    ("GET", "/lotes", None),
    ("GET", "/lotes/sugeridos", None),
    ("GET", "/lotes/1", None),
    ("GET", "/lotes/1/prevalidacion", None),
    ("GET", "/lotes/1/validacion-oficial", None),
    # 2026-11-12: el jefe tambien consulta los acuses (Tabla 46).
    ("GET", "/lotes/1/acuses", None),
)
# (metodo, ruta, cuerpo) -- solo analista.
_RUTAS_SOLO_ANALISTA: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/lotes/1/remision-iafas", None),
    ("POST", "/lotes/1/monitoreo", None),
    ("POST", "/lotes/envio-susalud", _CUERPO_ENVIO_SUSALUD),
)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_lotes_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_LECTURA)
async def prueba_lectura_de_lotes_con_rol_incorrecto_devuelve_403(
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


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.JEFE])
@pytest.mark.parametrize("caso", _RUTAS_LECTURA)
async def prueba_lectura_de_lotes_con_rol_correcto_no_devuelve_401_ni_403(
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
async def prueba_ruta_solo_analista_de_lotes_sin_token_devuelve_401(
    cliente: AsyncClient, metodo: str, ruta: str, cuerpo: dict[str, Any] | None
) -> None:
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_lotes_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    # JEFE tiene acceso de lectura a lotes pero no a estas rutas: confirma
    # que el filtro es realmente "solo analista" y no "cualquier lector".
    token = await token_para_rol(NombreRol.JEFE)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", _RUTAS_SOLO_ANALISTA)
async def prueba_ruta_solo_analista_de_lotes_con_rol_correcto_no_devuelve_401_ni_403(
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


async def prueba_un_acceso_denegado_queda_en_la_bitacora(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """RT-10 y C-08: el intento sin permiso se registra con la operacion."""
    token = await token_para_rol(NombreRol.TESORERIA)
    respuesta = await cliente.get("/lotes", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403
    async with fabrica_sesiones() as sesion:
        filas = (
            await sesion.execute(
                sa.select(EventoModelo.datos).where(EventoModelo.tipo_evento == "ACCESO_DENEGADO")
            )
        ).all()
    assert [fila[0] for fila in filas] == [{"metodo": "GET", "ruta": "/lotes"}]


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.JEFE])
async def prueba_validar_el_lote_es_del_analista_y_del_jefe(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    """Tabla 46: "Generar y validar el lote", analista y jefe."""
    token = await token_para_rol(rol)
    respuesta = await cliente.post(
        "/lotes/1/carga-validador", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)


async def prueba_validar_el_lote_no_es_del_auditor(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.AUDITOR)
    respuesta = await cliente.post(
        "/lotes/1/carga-validador", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403
