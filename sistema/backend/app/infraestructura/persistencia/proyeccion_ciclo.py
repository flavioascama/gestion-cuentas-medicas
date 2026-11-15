"""Proyeccion de lectura del ciclo de cada cuenta (RNF-04, RAS-04, AD-04,
RF-15): lo que el panel gerencial necesita de los eventos de la cuenta,
acumulado al registrar cada evento, para no recorrer el almacen en cada
consulta.

Por cuenta: el estado que dicen sus eventos, el primer y el ultimo cambio
de estado, el cierre, si tuvo glosa, y por cada estado alcanzado la suma
de horas y la cantidad de transiciones que lo alcanzaron (la duracion de
una transicion se asigna al estado al que llega, la misma regla que usaba
el calculo en la consulta).

La proyeccion es derivada: `reconstruir_proyecciones` la vuelve a calcular
desde el almacen de eventos, que sigue siendo la fuente autoritativa
(RAS-03). `version_evento` hace la aplicacion idempotente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base

TIPOS_EVENTO_GLOSA = frozenset({"GLOSA", "GLOSA_PARCIAL"})


class ProyeccionCicloCuentaModelo(Base):
    __tablename__ = "proyeccion_ciclo_cuenta"

    # Sin llave foranea: es una estructura derivada, se reconstruye entera.
    cuenta_medica_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    estado: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    primer_cambio_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    ultimo_cambio_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    cerrada_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    glosada: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    # {estado: [horas_acumuladas, transiciones]}
    tiempos: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    version_evento: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)


def _utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class EventoProyectable:
    """Objeto de parametros: lo que la proyeccion toma de un evento."""

    cuenta_medica_id: int
    version: int
    tipo_evento: str
    estado_nuevo: str | None
    ocurrido_en: datetime


async def aplicar_evento_a_proyeccion(sesion: AsyncSession, evento: EventoProyectable) -> None:
    cuenta_medica_id, version = evento.cuenta_medica_id, evento.version
    tipo_evento, estado_nuevo, ocurrido_en = (
        evento.tipo_evento,
        evento.estado_nuevo,
        evento.ocurrido_en,
    )
    if estado_nuevo is None and tipo_evento not in TIPOS_EVENTO_GLOSA:
        return
    fila = await sesion.get(ProyeccionCicloCuentaModelo, cuenta_medica_id)
    if fila is None:
        fila = ProyeccionCicloCuentaModelo(
            cuenta_medica_id=cuenta_medica_id, glosada=False, tiempos={}, version_evento=0
        )
        sesion.add(fila)
    if version <= fila.version_evento:
        return
    fila.version_evento = version
    if tipo_evento in TIPOS_EVENTO_GLOSA:
        fila.glosada = True
    if estado_nuevo is None:
        return
    instante = _utc(ocurrido_en)
    if fila.ultimo_cambio_en is None:
        fila.primer_cambio_en = instante
    else:
        horas = max((instante - _utc(fila.ultimo_cambio_en)).total_seconds(), 0.0) / 3600
        tiempos = dict(fila.tiempos or {})
        acumulado, transiciones = tiempos.get(estado_nuevo, [0.0, 0])
        tiempos[estado_nuevo] = [acumulado + horas, transiciones + 1]
        fila.tiempos = tiempos
    fila.ultimo_cambio_en = instante
    fila.estado = estado_nuevo
    if estado_nuevo == "CERRADA":
        fila.cerrada_en = instante


async def reconstruir_proyecciones(
    sesion: AsyncSession, cuenta_ids: list[int] | None = None
) -> int:
    """Vuelve a calcular la proyeccion desde el almacen (todas las cuentas
    o las indicadas). Devuelve cuantas cuentas quedaron proyectadas."""
    from app.infraestructura.persistencia.modelos_integracion import EventoModelo

    borrar = sa.delete(ProyeccionCicloCuentaModelo)
    consulta = sa.select(
        EventoModelo.agregado_id,
        EventoModelo.version,
        EventoModelo.tipo_evento,
        EventoModelo.estado_nuevo,
        EventoModelo.ocurrido_en,
    ).where(EventoModelo.tipo_agregado == "CUENTA")
    if cuenta_ids is not None:
        borrar = borrar.where(ProyeccionCicloCuentaModelo.cuenta_medica_id.in_(cuenta_ids))
        consulta = consulta.where(EventoModelo.agregado_id.in_(cuenta_ids))
    await sesion.execute(borrar)
    await sesion.flush()
    filas = await sesion.execute(consulta.order_by(EventoModelo.agregado_id, EventoModelo.version))
    for agregado_id, version, tipo_evento, estado_nuevo, ocurrido_en in filas.all():
        await aplicar_evento_a_proyeccion(
            sesion, EventoProyectable(agregado_id, version, tipo_evento, estado_nuevo, ocurrido_en)
        )
    await sesion.flush()
    return int(
        await sesion.scalar(sa.select(sa.func.count()).select_from(ProyeccionCicloCuentaModelo))
        or 0
    )
