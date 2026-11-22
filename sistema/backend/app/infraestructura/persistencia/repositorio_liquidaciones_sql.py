"""Adaptador de RepositorioLiquidaciones (Seccion 5.2.4.1, Fase 28)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.liquidacion.casos_uso import TIPO_EVENTO_PAGO_ADICIONAL
from app.dominio.liquidacion.puertos import RepositorioLiquidaciones
from app.dominio.liquidacion.valores import DatosNuevaLiquidacion, Liquidacion
from app.dominio.orquestacion.valores import TipoTransicion
from app.infraestructura.persistencia.modelos_integracion import EventoModelo
from app.infraestructura.persistencia.modelos_liquidacion import LiquidacionModelo
from app.infraestructura.persistencia.repositorio_documentos_pago_sql import (
    RepositorioDocumentosPagoSql,
)

_TIPOS_REGISTRO = (TipoTransicion.LIQUIDACION.value, TipoTransicion.LIQUIDACION_PARCIAL.value)
_TIPOS_PAGO = (
    TipoTransicion.CONCILIACION_PAGO.value,
    TipoTransicion.CONCILIACION_PAGO_PARCIAL.value,
    TIPO_EVENTO_PAGO_ADICIONAL,
)


async def total_facturado_de_cuenta(sesion: AsyncSession, cuenta_medica_id: int) -> Decimal | None:
    """El total del comprobante vigente, tal como lo muestra la seccion de
    liquidacion de la cuenta."""
    documentos = await RepositorioDocumentosPagoSql(sesion).documentos(cuenta_medica_id)
    return documentos.vigente.total if documentos is not None else None


def _a_valor(fila: LiquidacionModelo) -> Liquidacion:
    return Liquidacion(
        id=fila.id,
        cuenta_medica_id=fila.cuenta_medica_id,
        es_parcial=fila.es_parcial,
        monto_liquidado=fila.monto_liquidado,
        registrado_en=fila.registrado_en,
        monto_pagado=fila.monto_pagado,
        diferencia=fila.diferencia,
        conciliado_en=fila.conciliado_en,
    )


class RepositorioLiquidacionesSql(RepositorioLiquidaciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear(self, datos: DatosNuevaLiquidacion) -> int:
        fila = LiquidacionModelo(
            cuenta_medica_id=datos.cuenta_medica_id,
            es_parcial=datos.es_parcial,
            monto_liquidado=datos.monto_liquidado,
            registrado_en=datos.registrado_en,
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        return fila.id

    async def obtener_por_cuenta(self, cuenta_medica_id: int) -> Liquidacion | None:
        fila = (
            await self._sesion.execute(
                sa.select(LiquidacionModelo).where(
                    LiquidacionModelo.cuenta_medica_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()
        return None if fila is None else _a_valor(fila)

    async def actor_del_registro(self, liquidacion: Liquidacion) -> str | None:
        actor: str | None = await self._sesion.scalar(
            sa.select(EventoModelo.actor)
            .where(
                EventoModelo.cuenta_medica_id == liquidacion.cuenta_medica_id,
                EventoModelo.tipo_evento.in_(_TIPOS_REGISTRO),
                EventoModelo.datos["liquidacion_id"].as_integer() == liquidacion.id,
            )
            .order_by(EventoModelo.version)
            .limit(1)
        )
        return actor

    async def total_facturado(self, cuenta_medica_id: int) -> Decimal | None:
        return await total_facturado_de_cuenta(self._sesion, cuenta_medica_id)

    async def actores_del_pago(self, liquidacion: Liquidacion) -> list[str | None]:
        actores = await self._sesion.scalars(
            sa.select(EventoModelo.actor)
            .where(
                EventoModelo.cuenta_medica_id == liquidacion.cuenta_medica_id,
                EventoModelo.tipo_evento.in_(_TIPOS_PAGO),
                EventoModelo.datos["liquidacion_id"].as_integer() == liquidacion.id,
            )
            .order_by(EventoModelo.version)
        )
        return list(actores)

    async def corregir_monto(self, liquidacion_id: int, monto_liquidado: Decimal) -> None:
        await self._sesion.execute(
            sa.update(LiquidacionModelo)
            .where(LiquidacionModelo.id == liquidacion_id)
            .values(monto_liquidado=monto_liquidado)
        )

    async def conciliar(
        self,
        liquidacion_id: int,
        monto_pagado: Decimal,
        diferencia: Decimal,
        conciliado_en: datetime,
    ) -> None:
        await self._sesion.execute(
            sa.update(LiquidacionModelo)
            .where(LiquidacionModelo.id == liquidacion_id)
            .values(monto_pagado=monto_pagado, diferencia=diferencia, conciliado_en=conciliado_en)
        )

    async def registrar_pago_adicional(
        self, liquidacion_id: int, monto_pagado: Decimal, diferencia: Decimal
    ) -> None:
        await self._sesion.execute(
            sa.update(LiquidacionModelo)
            .where(LiquidacionModelo.id == liquidacion_id)
            .values(monto_pagado=monto_pagado, diferencia=diferencia)
        )
