"""Pruebas de autorizacion por ruta de /correos-iafas y del remitente de la
aseguradora (2026-11-15). Leen los correos el analista, el auditor medico,
el jefe y tesoreria; vinculan o descartan el analista y el jefe; el
remitente autorizado lo registra el administrador. Ademas, que la consulta
y la descarga dejen su evento en la bitacora (C-08)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.comunicaciones.correos import (
    AdjuntoRecibido,
    CorreoPorRegistrar,
    CorreoRecibido,
    EstadoCorreo,
    MotivoRevision,
    evaluar_adjuntos,
    huella_de,
)
from app.infraestructura.persistencia.modelos_integracion import EventoModelo, IafasModelo
from app.infraestructura.persistencia.repositorio_correos_sql import RepositorioCorreosSql

TokenParaRol = Callable[[NombreRol], Awaitable[str]]
Ruta = tuple[str, str, dict[str, Any] | None]

_LECTORES = [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA]
_NO_LECTORES = [NombreRol.GERENTE, NombreRol.ADMINISTRADOR]
_REVISORES = [NombreRol.ANALISTA, NombreRol.JEFE]
_NO_REVISORES = [
    NombreRol.AUDITOR,
    NombreRol.TESORERIA,
    NombreRol.GERENTE,
    NombreRol.ADMINISTRADOR,
]

_RUTAS_LECTURA: tuple[Ruta, ...] = (
    ("GET", "/correos-iafas", None),
    ("GET", "/correos-iafas/1", None),
    ("GET", "/correos-iafas/1/adjuntos/1", None),
)
_RUTAS_REVISION: tuple[Ruta, ...] = (
    ("POST", "/correos-iafas/1/vinculacion", {"identificacion_interna": "CM-0000001"}),
    ("POST", "/correos-iafas/1/descarte", {"motivo": "No corresponde a la clínica"}),
)
_RUTA_REMITENTE: Ruta = (
    "PUT",
    "/parametros/iafas/1/correo-remitente",
    {"correo_remitente": "auditoria@iafas.test"},
)
_PDF = b"%PDF-1.4 documento de prueba"


def _encabezado(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("caso", [*_RUTAS_LECTURA, *_RUTAS_REVISION, _RUTA_REMITENTE])
async def prueba_rutas_de_correos_sin_token_devuelven_401(cliente: AsyncClient, caso: Ruta) -> None:
    metodo, ruta, cuerpo = caso
    respuesta = await cliente.request(metodo, ruta, json=cuerpo)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("rol", _NO_LECTORES)
@pytest.mark.parametrize("caso", _RUTAS_LECTURA)
async def prueba_lectura_de_correos_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient, token_para_rol: TokenParaRol, caso: Ruta, rol: NombreRol
) -> None:
    metodo, ruta, cuerpo = caso
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers=_encabezado(await token_para_rol(rol))
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", _LECTORES)
@pytest.mark.parametrize("caso", _RUTAS_LECTURA)
async def prueba_lectura_de_correos_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient, token_para_rol: TokenParaRol, caso: Ruta, rol: NombreRol
) -> None:
    metodo, ruta, cuerpo = caso
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers=_encabezado(await token_para_rol(rol))
    )
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("rol", _NO_REVISORES)
@pytest.mark.parametrize("caso", _RUTAS_REVISION)
async def prueba_revision_de_correos_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient, token_para_rol: TokenParaRol, caso: Ruta, rol: NombreRol
) -> None:
    metodo, ruta, cuerpo = caso
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers=_encabezado(await token_para_rol(rol))
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", _REVISORES)
@pytest.mark.parametrize("caso", _RUTAS_REVISION)
async def prueba_revision_de_correos_con_rol_correcto_no_devuelve_401_ni_403(
    cliente: AsyncClient, token_para_rol: TokenParaRol, caso: Ruta, rol: NombreRol
) -> None:
    metodo, ruta, cuerpo = caso
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers=_encabezado(await token_para_rol(rol))
    )
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("rol", [rol for rol in NombreRol if rol is not NombreRol.ADMINISTRADOR])
async def prueba_remitente_de_la_iafas_solo_lo_registra_el_administrador(
    cliente: AsyncClient, token_para_rol: TokenParaRol, rol: NombreRol
) -> None:
    metodo, ruta, cuerpo = _RUTA_REMITENTE
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers=_encabezado(await token_para_rol(rol))
    )
    assert respuesta.status_code == 403


async def _sembrar(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    """Una IAFAS y un correo por revisar con un PDF; devuelve sus ids."""
    adjuntos = (AdjuntoRecibido("informe.pdf", "application/pdf", _PDF),)
    async with fabrica_sesiones() as sesion:
        iafas = IafasModelo(
            codigo="96969",
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=30,
            ventana_monitoreo_horas=72,
        )
        sesion.add(iafas)
        await sesion.commit()
        correo_id = await RepositorioCorreosSql(sesion).registrar(
            CorreoPorRegistrar(
                correo=CorreoRecibido(
                    huella=huella_de(b"correo de prueba"),
                    remitente="auditoria@iafas.test",
                    asunto="Solicitud de documentación",
                    fecha=None,
                    texto="Necesitamos el informe médico.",
                    adjuntos=adjuntos,
                    comunicacion=None,
                ),
                codigo_iafas=None,
                estado=EstadoCorreo.POR_REVISAR,
                motivo_revision=MotivoRevision.REMITENTE_NO_REGISTRADO,
                comunicacion_codigo=None,
                cuenta_medica_id=None,
                adjuntos=evaluar_adjuntos(adjuntos),
            ),
            datetime(2026, 11, 15, 10, 0, 0),
        )
        return iafas.id, correo_id


async def _tipos_de_evento(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> list[str]:
    async with fabrica_sesiones() as sesion:
        filas = await sesion.execute(sa.select(EventoModelo.tipo_evento))
        return [fila[0] for fila in filas.all()]


async def prueba_recorrido_de_un_correo_por_revisar(
    cliente: AsyncClient,
    token_para_rol: TokenParaRol,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    _, correo_id = await _sembrar(fabrica_sesiones)
    analista = _encabezado(await token_para_rol(NombreRol.ANALISTA))

    bandeja = await cliente.get(
        "/correos-iafas", params={"estado": "POR_REVISAR"}, headers=analista
    )
    assert bandeja.status_code == 200
    (fila,) = bandeja.json()
    # La bandeja no entrega el texto ni los adjuntos: solo el detalle.
    assert fila["id"] == correo_id and "texto" not in fila and "adjuntos" not in fila
    assert fila["cantidad_adjuntos"] == 1

    detalle = await cliente.get(f"/correos-iafas/{correo_id}", headers=analista)
    assert detalle.status_code == 200
    assert detalle.json()["texto"] == "Necesitamos el informe médico."
    adjunto = detalle.json()["adjuntos"][0]

    descarga = await cliente.get(
        f"/correos-iafas/{correo_id}/adjuntos/{adjunto['id']}", headers=analista
    )
    assert descarga.status_code == 200
    assert descarga.content == _PDF
    assert descarga.headers["content-type"] == "application/octet-stream"
    assert descarga.headers["content-disposition"].startswith("attachment")
    assert descarga.headers["x-content-type-options"] == "nosniff"

    corto = await cliente.post(
        f"/correos-iafas/{correo_id}/descarte", json={"motivo": "no"}, headers=analista
    )
    assert corto.status_code == 422
    sin_cuenta = await cliente.post(
        f"/correos-iafas/{correo_id}/vinculacion",
        json={"identificacion_interna": "CM-9999999"},
        headers=analista,
    )
    assert sin_cuenta.status_code == 404

    descarte = await cliente.post(
        f"/correos-iafas/{correo_id}/descarte",
        json={"motivo": "Publicidad de un proveedor"},
        headers=analista,
    )
    assert descarte.status_code == 200
    assert descarte.json()["estado"] == "DESCARTADO"
    assert descarte.json()["nota_resolucion"] == "Publicidad de un proveedor"
    repetido = await cliente.post(
        f"/correos-iafas/{correo_id}/descarte",
        json={"motivo": "Publicidad de un proveedor"},
        headers=analista,
    )
    assert repetido.status_code == 409

    eventos = await _tipos_de_evento(fabrica_sesiones)
    for esperado in (
        "CORREO_IAFAS_CONSULTADO",
        "ADJUNTO_CORREO_IAFAS_DESCARGADO",
        "CORREO_IAFAS_DESCARTADO",
    ):
        assert esperado in eventos
    assert await cliente.get("/correos-iafas/999", headers=analista) is not None
    assert (await cliente.get("/correos-iafas/999", headers=analista)).status_code == 404


async def prueba_el_administrador_registra_el_remitente_de_la_iafas(
    cliente: AsyncClient,
    token_para_rol: TokenParaRol,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    iafas_id, _ = await _sembrar(fabrica_sesiones)
    administrador = _encabezado(await token_para_rol(NombreRol.ADMINISTRADOR))
    ruta = f"/parametros/iafas/{iafas_id}/correo-remitente"

    invalido = await cliente.put(
        ruta, json={"correo_remitente": "sin arroba"}, headers=administrador
    )
    assert invalido.status_code == 400
    guardado = await cliente.put(
        ruta, json={"correo_remitente": " Auditoria@IAFAS.test "}, headers=administrador
    )
    assert guardado.status_code == 200
    assert guardado.json()["correo_remitente"] == "auditoria@iafas.test"
    listado = await cliente.get("/parametros/iafas", headers=administrador)
    assert listado.json()[0]["correo_remitente"] == "auditoria@iafas.test"
    assert "PARAMETROS_IAFAS_ACTUALIZADOS" in await _tipos_de_evento(fabrica_sesiones)
    inexistente = await cliente.put(
        "/parametros/iafas/999/correo-remitente",
        json={"correo_remitente": "auditoria@iafas.test"},
        headers=administrador,
    )
    assert inexistente.status_code == 404
