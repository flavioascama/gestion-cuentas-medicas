"""Adaptador de RepositorioParametrosIafas (CU-18)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.plazos.parametros import ParametrosIafas, RepositorioParametrosIafas
from app.infraestructura.persistencia.modelos_integracion import IafasModelo


def _a_parametros(fila: IafasModelo) -> ParametrosIafas:
    return ParametrosIafas(
        iafas_id=fila.id,
        codigo=fila.codigo,
        razon_social=fila.razon_social,
        periodicidad_remision_dias=fila.periodicidad_remision_dias,
        ventana_monitoreo_horas=fila.ventana_monitoreo_horas,
        dias_plazo_respuesta_observacion=fila.dias_plazo_respuesta_observacion,
        dias_plazo_comunicacion_auditoria=fila.dias_plazo_comunicacion_auditoria,
        dias_plazo_pago_liquidacion=fila.dias_plazo_pago_liquidacion,
    )


class RepositorioParametrosIafasSql(RepositorioParametrosIafas):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(self) -> list[ParametrosIafas]:
        filas = await self._sesion.execute(sa.select(IafasModelo).order_by(IafasModelo.codigo))
        return [_a_parametros(fila) for fila in filas.scalars().all()]

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None:
        fila = await self._sesion.get(IafasModelo, iafas_id)
        return _a_parametros(fila) if fila is not None else None

    async def actualizar(self, iafas_id: int, cambios: dict[str, int]) -> ParametrosIafas:
        await self._sesion.execute(
            sa.update(IafasModelo).where(IafasModelo.id == iafas_id).values(**cambios)
        )
        fila = await self._sesion.get(IafasModelo, iafas_id, populate_existing=True)
        assert fila is not None
        return _a_parametros(fila)
