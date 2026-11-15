"""Pruebas de RepositorioContingenciaSql contra SQLite en memoria: la
habilitacion se lee del ultimo trabajo de esa cuenta o lote (carga_util en
JSON), y la revision se deriva de los eventos sin tabla mutable. Mas la
autorizacion de las rutas (Tabla 46: registrar, solo el analista; C-18:
revisar, solo el jefe)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.contingencia.valores import EstadoRevision, TipoOperacion
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_contingencia_sql import (
    RepositorioContingenciaSql,
)
from pruebas.prueba_repositorio_monitoreo_respuesta import _sembrar_lote_remitido

_INICIO = datetime(2026, 11, 12, 8, 0, 0, tzinfo=UTC)


def _trabajo(tipo: str, carga: dict[str, object], estado: str, minutos: int) -> TrabajoModelo:
    instante = _INICIO + timedelta(minutes=minutos)
    return TrabajoModelo(
        tipo=tipo,
        carga_util=carga,
        estado=estado,
        intentos=5,
        proximo_intento=instante,
        creado_en=instante,
        actualizado_en=instante,
    )


async def prueba_lee_el_ultimo_trabajo_de_esa_cuenta_o_lote(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        sesion.add_all(
            [
                _trabajo("CONSULTAR_COBERTURA", {"cuenta_medica_id": 1}, "AGOTADO", 0),
                _trabajo("CONSULTAR_COBERTURA", {"cuenta_medica_id": 2}, "AGOTADO", 0),
                # La cuenta 2 se volvio a pedir despues y esta en curso.
                _trabajo("CONSULTAR_COBERTURA", {"cuenta_medica_id": 2}, "PENDIENTE", 5),
                _trabajo("CARGAR_LOTE_VALIDADOR", {"lote_id": 1}, "COMPLETADO", 0),
            ]
        )
        await sesion.commit()
        repositorio = RepositorioContingenciaSql(sesion)

        async def estado(tipo: str, clave: str, valor: int) -> str | None:
            ultimo = await repositorio.ultimo_trabajo(tipo, clave, valor)
            return ultimo.estado if ultimo else None

        assert await estado("CONSULTAR_COBERTURA", "cuenta_medica_id", 1) == "AGOTADO"
        # La cuenta 2 se volvio a pedir despues: cuenta la mas reciente.
        assert await estado("CONSULTAR_COBERTURA", "cuenta_medica_id", 2) == "PENDIENTE"
        assert await estado("CONSULTAR_COBERTURA", "cuenta_medica_id", 3) is None
        assert await estado("CARGAR_LOTE_VALIDADOR", "lote_id", 1) == "COMPLETADO"


async def prueba_registros_y_su_revision_se_derivan_de_los_eventos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, cuenta_id = await _sembrar_lote_remitido(sesion)
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CONTINGENCIA_COBERTURA_REGISTRADA",
                actor="ana",
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "condicion_cobertura": "ACREDITABLE",
                    "codigo_autorizacion": "AUT-1",
                    "sustento": "constancia de la IAFAS",
                },
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento="CONTINGENCIA_VALIDACION_REGISTRADA",
                actor="ana",
                estado_previo="GENERADO",
                estado_nuevo="OBSERVADO_VALIDADOR",
                datos={"resultado": "OBSERVADO", "sustento": "constancia del validador"},
            )
        )
        repositorio = RepositorioContingenciaSql(sesion)
        cobertura = next(
            r for r in await repositorio.listar_registros() if r.cuenta_medica_id == cuenta_id
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CONTINGENCIA_REVISADA",
                actor="jefe",
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "registro_evento_id": cobertura.evento_id,
                    "conforme": False,
                    "comentario": "falta constancia",
                },
            )
        )

        registros = {r.tipo_operacion: r for r in await repositorio.listar_registros()}

    assert set(registros) == {TipoOperacion.COBERTURA, TipoOperacion.VALIDACION}
    revisada = registros[TipoOperacion.COBERTURA]
    assert revisada.estado_revision is EstadoRevision.NO_CONFORME
    assert (revisada.revisado_por, revisada.comentario_revision) == ("jefe", "falta constancia")
    assert revisada.resumen == "Cobertura ACREDITABLE, autorización AUT-1"
    pendiente = registros[TipoOperacion.VALIDACION]
    assert pendiente.estado_revision is EstadoRevision.PENDIENTE
    assert (pendiente.lote_id, pendiente.numero_lote) == (lote_id, "0000001")
    assert pendiente.sustento == "constancia del validador"


_RUTAS_ANALISTA = (
    ("GET", "/cuentas/1/cobertura/contingencia"),
    ("GET", "/lotes/1/validacion/contingencia"),
)


@pytest.mark.parametrize("metodo,ruta", _RUTAS_ANALISTA)
async def prueba_contingencia_es_del_analista(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    metodo: str,
    ruta: str,
) -> None:
    assert (await cliente.request(metodo, ruta)).status_code == 401
    jefe = await token_para_rol(NombreRol.JEFE)
    analista = await token_para_rol(NombreRol.ANALISTA)
    respuesta_jefe = await cliente.request(
        metodo, ruta, headers={"Authorization": f"Bearer {jefe}"}
    )
    respuesta_analista = await cliente.request(
        metodo, ruta, headers={"Authorization": f"Bearer {analista}"}
    )
    assert respuesta_jefe.status_code == 403
    assert respuesta_analista.status_code == 200
    assert respuesta_analista.json() == {"habilitada": False}


async def prueba_revision_de_contingencia_es_del_jefe(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    analista = await token_para_rol(NombreRol.ANALISTA)
    jefe = await token_para_rol(NombreRol.JEFE)
    assert (
        await cliente.get("/contingencias", headers={"Authorization": f"Bearer {analista}"})
    ).status_code == 403
    respuesta = await cliente.get("/contingencias", headers={"Authorization": f"Bearer {jefe}"})
    assert respuesta.status_code == 200 and respuesta.json() == []
    inexistente = await cliente.post(
        "/contingencias/no-existe/revision",
        json={"conforme": True},
        headers={"Authorization": f"Bearer {jefe}"},
    )
    assert inexistente.status_code == 404
