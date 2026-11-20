"""Apoyo de las pruebas de integracion que saltan etapas del ciclo ya
probadas por separado (por ejemplo, llevar una cuenta directo a
EN_AUDITORIA sin generar ni remitir un lote).

Fijar el estado solo por SQL dejaria el almacen de eventos con otro ultimo
estado, y el primer evento real posterior violaria la regla de continuidad
(Tabla 69) que `RegistroEventosSql.registrar` exige. Por eso el estado
fijado queda tambien como evento de partida, sin estado previo."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql


async def liberar_cuenta_de_lotes_en_curso(sesion: AsyncSession, cuenta_id: int) -> None:
    """Las cuentas dedicadas de un escenario se reutilizan en cada corrida
    y una cuenta que sigue en un lote en curso no entra en otro
    (2026-11-19). Los lotes que dejaron las corridas anteriores se dan por
    observados, que es el estado que libera sus cuentas para un lote nuevo."""
    await sesion.execute(
        sa.text(
            "update lote_facturacion set estado = 'OBSERVADO_VALIDADOR' "
            "where estado in ('GENERADO', 'CARGADO_VALIDADOR', 'VALIDADO') and id in ("
            "select ld.lote_id from lote_documento ld "
            "join documento_facturador d on d.id = ld.documento_id "
            "where d.cuenta_id = :cuenta)"
        ),
        {"cuenta": cuenta_id},
    )
    await sesion.commit()


async def fijar_estado_de_prueba(sesion: AsyncSession, cuenta_id: int, estado: str) -> None:
    await sesion.execute(
        sa.update(CuentaMedicaModelo)
        .where(CuentaMedicaModelo.id == cuenta_id)
        .values(estado=estado)
    )
    await RegistroEventosSql(sesion).registrar(
        Evento(
            cuenta_medica_id=cuenta_id,
            tipo_evento="ESTADO_FIJADO_EN_PRUEBA",
            actor="integracion_prueba",
            estado_previo=None,
            estado_nuevo=estado,
        )
    )
