"""Transicion de todas las cuentas de un lote, validada contra el motor de
orquestacion (RF-08, Tabla 58). La comparten la remision (T-03, Seccion
7.8) y la respuesta del receptor (T-04/T-06, Seccion 8.3): antes solo la
respuesta pasaba por el motor y la remision escribia `ENVIADA` sin
ninguna guarda (verificacion de cumplimiento del 12 de noviembre)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import TipoTransicion
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
)


async def cuentas_de_documentos(
    sesion: AsyncSession, documento_ids: tuple[int, ...]
) -> tuple[int, ...]:
    if not documento_ids:
        return ()
    resultado = await sesion.execute(
        sa.select(DocumentoFacturadorModelo.cuenta_id)
        .where(DocumentoFacturadorModelo.id.in_(documento_ids))
        .order_by(DocumentoFacturadorModelo.cuenta_id)
    )
    return tuple(fila[0] for fila in resultado.all())


async def transicionar_cuentas(
    sesion: AsyncSession, cuenta_medica_ids: tuple[int, ...], transicion: TipoTransicion
) -> None:
    """Las cuentas de un mismo lote llegan desde el mismo estado, asi que
    basta validar una vez por cada estado distinto encontrado. Si hubiera
    mas de un estado resultante es una inconsistencia de datos, y conviene
    que falle aqui y no a mitad del UPDATE."""

    if not cuenta_medica_ids:
        return
    estados_actuales = (
        await sesion.execute(
            sa.select(CuentaMedicaModelo.estado)
            .where(CuentaMedicaModelo.id.in_(cuenta_medica_ids))
            .distinct()
        )
    ).scalars()
    estados_resultantes = {
        validar_transicion(estado_actual, transicion) for estado_actual in estados_actuales
    }
    (estado_nuevo,) = estados_resultantes
    await sesion.execute(
        sa.update(CuentaMedicaModelo)
        .where(CuentaMedicaModelo.id.in_(cuenta_medica_ids))
        .values(estado=estado_nuevo)
    )
