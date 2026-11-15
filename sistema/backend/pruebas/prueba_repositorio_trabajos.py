"""Pruebas de RepositorioTrabajosSql contra SQLite en memoria (Seccion
6.1, 6.2): encolar y las tres formas de cerrar un trabajo. `tomar_siguiente`
usa `SELECT ... FOR UPDATE SKIP LOCKED` (AD-03), que SQLite no soporta de
verdad -- se verifica aparte, contra Postgres real en Docker (mismo
patron que `RepositorioLoteFacturacionSql.siguiente_numero_lote` en la
Fase 7, docs/DECISIONES.md)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo


async def prueba_encolar_crea_un_trabajo_pendiente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            tipo="CONSULTAR_COBERTURA",
            carga_util={"cuenta_medica_id": 1},
            proximo_intento=datetime(2026, 9, 18, 10, 0, 0),
        )
        assert trabajo_id > 0

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.estado == "PENDIENTE"
        assert trabajo.intentos == 0
        assert trabajo.carga_util == {"cuenta_medica_id": 1}


async def prueba_marcar_completado(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 18, 10, 0, 0)
        )
        await repositorio.marcar_completado(trabajo_id)

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.estado == "COMPLETADO"


async def prueba_marcar_para_reintento_incrementa_intentos_y_vuelve_a_pendiente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 18, 10, 0, 0)
        )
        nuevo_proximo_intento = datetime(2026, 9, 18, 10, 15, 0)
        await repositorio.marcar_para_reintento(trabajo_id, "error de red", nuevo_proximo_intento)

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.estado == "PENDIENTE"
        assert trabajo.intentos == 1
        assert trabajo.error == "error de red"
        assert trabajo.proximo_intento == nuevo_proximo_intento


async def prueba_marcar_agotado(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 18, 10, 0, 0)
        )
        await repositorio.marcar_agotado(trabajo_id, "maximo de reintentos superado")

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.estado == "AGOTADO"
        assert trabajo.intentos == 1
        assert trabajo.error == "maximo de reintentos superado"


async def prueba_marcar_requiere_sesion(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 25, 10, 0, 0)
        )
        await repositorio.marcar_requiere_sesion(trabajo_id)

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.estado == "REQUIERE_SESION"
        assert trabajo.intentos == 0  # Seccion 8.4, punto 6: "sin consumir intentos"


async def prueba_reactivar_requieren_sesion_solo_afecta_los_tipos_pedidos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        id_cobertura = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 25, 10, 0, 0)
        )
        id_otro_tipo = await repositorio.encolar("OTRO_TIPO", {}, datetime(2026, 9, 25, 10, 0, 0))
        await repositorio.marcar_requiere_sesion(id_cobertura)
        await repositorio.marcar_requiere_sesion(id_otro_tipo)

        reactivados = await repositorio.reactivar_requieren_sesion(("CONSULTAR_COBERTURA",))
        assert reactivados == 1

    async with fabrica_sesiones() as sesion:
        cobertura = await sesion.get(TrabajoModelo, id_cobertura)
        otro = await sesion.get(TrabajoModelo, id_otro_tipo)
        assert cobertura is not None and cobertura.estado == "PENDIENTE"
        assert otro is not None and otro.estado == "REQUIERE_SESION"


async def prueba_marcar_para_reintento_trunca_el_error_muy_largo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioTrabajosSql(sesion)
        trabajo_id = await repositorio.encolar(
            "CONSULTAR_COBERTURA", {}, datetime(2026, 9, 18, 10, 0, 0)
        )
        await repositorio.marcar_para_reintento(
            trabajo_id, "x" * 2000, datetime(2026, 9, 18, 10, 15, 0)
        )

    async with fabrica_sesiones() as sesion:
        trabajo = await sesion.get(TrabajoModelo, trabajo_id)
        assert trabajo is not None
        assert trabajo.error is not None
        assert len(trabajo.error) == 1000
