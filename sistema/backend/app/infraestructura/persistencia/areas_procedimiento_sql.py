"""Area de cada procedimiento facturado (2026-11-19): la del procedimiento
por codificar que confirma, si viene de una atencion importada; si no, la
que corresponde sin duda a su subseccion del catalogo CPMS; si no, queda
como procedimiento. Decide el Codigo Rubro (T3 campo 23) y el grupo de
gasto (T2 campos 35, 38 y 39)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.atencion_hospitalaria import AREA_PROCEDIMIENTO
from app.infraestructura.persistencia.modelos_atencion_hospitalaria import (
    ProcedimientoPorCodificarModelo,
)
from app.infraestructura.persistencia.modelos_cpms import CpmsProcedimientoModelo
from app.infraestructura.persistencia.modelos_integracion import ProcedimientoFacturadoModelo
from app.infraestructura.tedef.catalogos_atencion import AREA_POR_SUBSECCION_CPMS


async def _areas_de_origen(sesion: AsyncSession, ids: list[int]) -> dict[int, str]:
    filas = await sesion.execute(
        sa.select(
            ProcedimientoPorCodificarModelo.procedimiento_facturado_id,
            ProcedimientoPorCodificarModelo.area,
        ).where(ProcedimientoPorCodificarModelo.procedimiento_facturado_id.in_(ids))
    )
    return {procedimiento_id: area for procedimiento_id, area in filas.all() if procedimiento_id}


async def _areas_por_catalogo(sesion: AsyncSession, ids: list[int]) -> dict[int, str]:
    filas = await sesion.execute(
        sa.select(ProcedimientoFacturadoModelo.id, CpmsProcedimientoModelo.codigo_subseccion)
        .join(
            CpmsProcedimientoModelo,
            sa.and_(
                CpmsProcedimientoModelo.cpms_version_id
                == ProcedimientoFacturadoModelo.cpms_version_id,
                CpmsProcedimientoModelo.codigo_procedimiento
                == ProcedimientoFacturadoModelo.codigo_asignado,
            ),
        )
        .where(ProcedimientoFacturadoModelo.id.in_(ids))
    )
    return {
        procedimiento_id: AREA_POR_SUBSECCION_CPMS[subseccion]
        for procedimiento_id, subseccion in filas.all()
        if subseccion in AREA_POR_SUBSECCION_CPMS
    }


async def areas_de_procedimientos(
    sesion: AsyncSession, procedimiento_ids: Sequence[int]
) -> dict[int, str]:
    """Area de cada procedimiento pedido; nunca falta ninguno."""
    ids = list(procedimiento_ids)
    if not ids:
        return {}
    areas = await _areas_de_origen(sesion, ids)
    sin_origen = [i for i in ids if i not in areas]
    if sin_origen:
        areas.update(await _areas_por_catalogo(sesion, sin_origen))
    return {i: areas.get(i, AREA_PROCEDIMIENTO) for i in ids}
