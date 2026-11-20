"""Efecto de la revision NO CONFORME del jefe (control C-18) sobre lo
registrado en contingencia, leido de los eventos (registro y revision):

- cobertura: si la acreditacion vigente de la cuenta es la registrada a mano
  y su revision fue no conforme, no sirve para facturar;
- validacion: el lote cuya validacion registrada a mano fue revisada no
  conforme deja de estar vigente."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.contingencia.valores import (
    COMPONENTE_REGISTRO_MANUAL,
    TIPO_EVENTO_COBERTURA_CONTINGENCIA,
    TIPO_EVENTO_REVISION_CONTINGENCIA,
    TIPO_EVENTO_VALIDACION_CONTINGENCIA,
)
from app.dominio.puertos_comunes import TIPO_AGREGADO_LOTE
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    EventoModelo,
)


def _no_conformes(filas: Iterable[Any]) -> set[str]:
    """Ids de los registros cuya revision fue no conforme."""
    return {
        str((datos or {}).get("registro_evento_id"))
        for _agregado, _evento_id, tipo, datos in filas
        if tipo == TIPO_EVENTO_REVISION_CONTINGENCIA and not (datos or {}).get("conforme")
    }


async def acreditacion_vigente_no_conforme(sesion: AsyncSession, cuenta_id: int) -> bool:
    vigente = (
        await sesion.execute(
            sa.select(AcreditacionModelo.id, AcreditacionModelo.componente_ejecutor)
            .where(AcreditacionModelo.cuenta_id == cuenta_id)
            .order_by(AcreditacionModelo.id.desc())
            .limit(1)
        )
    ).first()
    if vigente is None or vigente[1] != COMPONENTE_REGISTRO_MANUAL:
        return False
    filas = (
        await sesion.execute(
            sa.select(
                EventoModelo.agregado_id,
                EventoModelo.evento_id,
                EventoModelo.tipo_evento,
                EventoModelo.datos,
            ).where(
                EventoModelo.cuenta_medica_id == cuenta_id,
                EventoModelo.tipo_evento.in_(
                    [TIPO_EVENTO_COBERTURA_CONTINGENCIA, TIPO_EVENTO_REVISION_CONTINGENCIA]
                ),
            )
        )
    ).all()
    no_conformes = _no_conformes(filas)
    return any(
        tipo == TIPO_EVENTO_COBERTURA_CONTINGENCIA
        and (datos or {}).get("acreditacion_id") == vigente[0]
        and str(evento_id) in no_conformes
        for _agregado, evento_id, tipo, datos in filas
    )


async def lotes_con_validacion_no_conforme(
    sesion: AsyncSession, lote_ids: Iterable[int]
) -> set[int]:
    ids = list(lote_ids)
    if not ids:
        return set()
    filas = (
        await sesion.execute(
            sa.select(
                EventoModelo.agregado_id,
                EventoModelo.evento_id,
                EventoModelo.tipo_evento,
                EventoModelo.datos,
            ).where(
                EventoModelo.tipo_agregado == TIPO_AGREGADO_LOTE,
                EventoModelo.agregado_id.in_(ids),
                EventoModelo.tipo_evento.in_(
                    [TIPO_EVENTO_VALIDACION_CONTINGENCIA, TIPO_EVENTO_REVISION_CONTINGENCIA]
                ),
            )
        )
    ).all()
    no_conformes = _no_conformes(filas)
    return {
        int(agregado)
        for agregado, evento_id, tipo, _datos in filas
        if tipo == TIPO_EVENTO_VALIDACION_CONTINGENCIA and str(evento_id) in no_conformes
    }
