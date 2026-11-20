"""Si la respuesta a una observacion de la aseguradora le llego
(2026-11-19). Al responder, la entrega por el portal queda encolada para
el robot; aqui se resume en que quedo: pendiente, entregada (con su fecha)
o no entregada (el trabajo agoto sus intentos). Solo aplica a las
observaciones que vinieron de la aseguradora y ya se respondieron."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.dominio.observaciones.valores import Observacion


class EstadoEntrega(StrEnum):
    PENDIENTE = "PENDIENTE"
    ENTREGADA = "ENTREGADA"
    NO_ENTREGADA = "NO_ENTREGADA"


@dataclass(frozen=True, slots=True)
class HechosEntrega:
    """De una observacion que llego de la aseguradora: cuando se entrego
    la respuesta, el estado del ultimo trabajo de entrega y quien pidio el
    primero (quien respondio)."""

    remitida_en: datetime | None
    estado_ultimo_trabajo: str | None
    solicitada_por: str | None


class ConsultaEntregas(Protocol):
    async def hechos(self, cuenta_medica_id: int) -> dict[int, HechosEntrega]:
        """Por id de observacion; solo las que vinieron de la aseguradora."""
        ...


def estado_entrega(observacion: Observacion, hechos: HechosEntrega | None) -> EstadoEntrega | None:
    if hechos is None or observacion.estado != "RESPONDIDA":
        return None
    if hechos.remitida_en is not None:
        return EstadoEntrega.ENTREGADA
    # Sin trabajo (respuesta anterior a la entrega por el robot) o agotado.
    if hechos.estado_ultimo_trabajo in (None, "AGOTADO"):
        return EstadoEntrega.NO_ENTREGADA
    return EstadoEntrega.PENDIENTE


def con_entrega(observacion: Observacion, hechos: HechosEntrega | None) -> Observacion:
    estado = estado_entrega(observacion, hechos)
    if estado is None or hechos is None:
        return observacion
    return replace(
        observacion,
        entrega_estado=estado.value,
        entrega_en=hechos.remitida_en,
        entrega_solicitada_por=hechos.solicitada_por,
    )
