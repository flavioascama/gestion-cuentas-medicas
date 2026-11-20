"""Volver a pedir la entrega de una respuesta a la aseguradora
(2026-11-19): cuando el trabajo de entrega agoto sus intentos sin
entregarla, quien respondio (o el analista) la encola otra vez, con la
misma respuesta guardada. Separado de casos_uso.py por el limite de lineas
por archivo."""

from __future__ import annotations

from dataclasses import dataclass

from app.dominio.acceso.entidades import NombreRol
from app.dominio.comunicaciones.casos_uso import EncolarRespuestaIafas
from app.dominio.observaciones.entrega import ConsultaEntregas, EstadoEntrega, estado_entrega
from app.dominio.observaciones.errores import ErrorObservacionInexistente
from app.dominio.observaciones.puertos import RepositorioObservaciones


class ErrorEntregaNoDisponible(Exception):
    """La observacion no vino de la aseguradora, no esta respondida, ya se
    entrego o su entrega sigue en curso."""


class ErrorEntregaDeOtro(Exception):
    """Solo quien respondio o el analista vuelven a pedir la entrega."""


@dataclass(frozen=True, slots=True)
class Solicitante:
    nombre_usuario: str
    roles: frozenset[NombreRol]


class SolicitarNuevaEntregaRespuesta:
    def __init__(
        self,
        observaciones: RepositorioObservaciones,
        entregas: ConsultaEntregas,
        encolar: EncolarRespuestaIafas,
    ) -> None:
        self._observaciones = observaciones
        self._entregas = entregas
        self._encolar = encolar

    async def ejecutar(self, observacion_id: int, solicitante: Solicitante) -> int:
        observacion = await self._observaciones.obtener(observacion_id)
        if observacion is None:
            raise ErrorObservacionInexistente(f"No existe la observacion {observacion_id}.")
        hechos = (await self._entregas.hechos(observacion.cuenta_medica_id)).get(observacion_id)
        if hechos is None or estado_entrega(observacion, hechos) is not EstadoEntrega.NO_ENTREGADA:
            raise ErrorEntregaNoDisponible(
                "La respuesta no esta pendiente de una nueva entrega a la aseguradora."
            )
        es_analista = NombreRol.ANALISTA in solicitante.roles
        if not es_analista and solicitante.nombre_usuario != hechos.solicitada_por:
            raise ErrorEntregaDeOtro("Solo quien respondio o el analista piden la entrega.")
        trabajo_id = await self._encolar.ejecutar(
            observacion_id,
            observacion.respuesta_texto or "",
            observacion.respuesta_sustento,
            solicitante.nombre_usuario,
        )
        if trabajo_id is None:
            raise ErrorEntregaNoDisponible("La observacion no vino de la aseguradora.")
        return trabajo_id
