"""Escenario "Inmutabilidad" de la Seccion 14.2 del plan v3 ("Como en la
v2") / Seccion 12.2 del v2: "UPDATE y DELETE sobre evento son rechazados
por la base de datos".

Los disparadores `trg_evento_sin_update`/`trg_evento_sin_delete`
(migracion `ab8ce7d4a79e`, funcion `fn_evento_inmutable`) son PL/pgSQL:
solo existen contra Postgres real, nunca contra el SQLite en memoria de
`pruebas/` (docs/DECISIONES.md, Fase 7: "hoy solo verificada a mano...
se formaliza" aqui, en la Fase 20)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import EventoModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql

# Fase 24: este evento de prueba no representa ninguna cuenta ni lote
# real, asi que usa el agregado "sesion de usuario" con un id centinela
# (0, nunca asignado a un usuario real) solo para satisfacer la regla de
# que todo evento pertenece a exactamente un agregado.
_USUARIO_ID_CENTINELA = 0


async def _insertar_evento_de_prueba(sesion: AsyncSession) -> uuid.UUID:
    registro = RegistroEventosSql(sesion)
    await registro.registrar(
        Evento(
            cuenta_medica_id=None,
            sesion_usuario_id=_USUARIO_ID_CENTINELA,
            tipo_evento="EVENTO_DE_PRUEBA_INMUTABILIDAD",
            actor="pruebas_integracion/prueba_inmutabilidad_evento.py",
            estado_previo=None,
            estado_nuevo=None,
            datos={"proposito": "verificar que UPDATE/DELETE son rechazados"},
        )
    )
    evento_id = (
        await sesion.execute(
            sa.select(EventoModelo.evento_id)
            .where(EventoModelo.tipo_evento == "EVENTO_DE_PRUEBA_INMUTABILIDAD")
            .order_by(EventoModelo.ocurrido_en.desc())
            .limit(1)
        )
    ).scalar_one()
    return evento_id


async def prueba_update_sobre_evento_es_rechazado_por_la_base_de_datos(
    sesion: AsyncSession,
) -> None:
    evento_id = await _insertar_evento_de_prueba(sesion)

    try:
        await sesion.execute(
            sa.update(EventoModelo)
            .where(EventoModelo.evento_id == evento_id)
            .values(tipo_evento="INTENTO_DE_MODIFICACION")
        )
        await sesion.commit()
        raise AssertionError("El UPDATE deberia haber sido rechazado por trg_evento_sin_update.")
    except DBAPIError as error:
        await sesion.rollback()
        assert "evento" in str(error.orig).lower() or "inmutable" in str(error.orig).lower()

    tipo_evento_actual = (
        await sesion.execute(
            sa.select(EventoModelo.tipo_evento).where(EventoModelo.evento_id == evento_id)
        )
    ).scalar_one()
    assert tipo_evento_actual == "EVENTO_DE_PRUEBA_INMUTABILIDAD"


async def prueba_delete_sobre_evento_es_rechazado_por_la_base_de_datos(
    sesion: AsyncSession,
) -> None:
    evento_id = await _insertar_evento_de_prueba(sesion)

    try:
        await sesion.execute(sa.delete(EventoModelo).where(EventoModelo.evento_id == evento_id))
        await sesion.commit()
        raise AssertionError("El DELETE deberia haber sido rechazado por trg_evento_sin_delete.")
    except DBAPIError as error:
        await sesion.rollback()
        assert "evento" in str(error.orig).lower() or "inmutable" in str(error.orig).lower()

    existe = (
        await sesion.execute(
            sa.select(sa.func.count())
            .select_from(EventoModelo)
            .where(EventoModelo.evento_id == evento_id)
        )
    ).scalar_one()
    assert existe == 1
