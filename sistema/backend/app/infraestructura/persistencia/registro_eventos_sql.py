"""Adaptador del puerto RegistroEventos (Seccion 6.3 y 6.2.2).

Calcula aqui, no en el dominio, los dos campos que dependen de lo que ya
hay guardado para el mismo agregado: `version` (su numero de orden) y
`hash_evento` (su encadenamiento con valor resumen con clave, RNF-18). El
bloqueo de fila sobre el ultimo evento del agregado (`FOR UPDATE`) evita
que dos inserciones concurrentes sobre el mismo agregado calculen la
misma `version` -- el mismo patron de `SELECT ... FOR UPDATE` que ya usa
`RepositorioTrabajosSql` para la cola (Seccion 5.2, AD-03), aplicado aqui
a nivel de agregado en vez de a nivel de fila de cola.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.configuracion import obtener_configuracion
from app.dominio.orquestacion.errores import ErrorContinuidadEstados, ErrorTransicionNoDefinida
from app.dominio.orquestacion.motor import transicion_definida
from app.dominio.orquestacion.valores import ESTADOS_CUENTA, ESTADOS_LOTE
from app.dominio.puertos_comunes import Evento, RegistroEventos
from app.infraestructura.persistencia.cadena_eventos import (
    GENESIS,
    DatosEventoParaHash,
    calcular_hash_evento,
)
from app.infraestructura.persistencia.modelos_integracion import EventoModelo
from app.infraestructura.persistencia.proyeccion_ciclo import (
    EventoProyectable,
    aplicar_evento_a_proyeccion,
)

# Evento compensatorio de herramientas/restablecer_continuidad_estados.py:
# une el ultimo estado registrado con el actual aunque no sea un paso de la
# Tabla 58 (el estado se habia fijado sin su evento).
_EVENTOS_COMPENSATORIOS = frozenset({"CONTINUIDAD_RESTABLECIDA"})


def _exigir_estados_definidos(evento: Evento) -> None:
    """Tabla 69 (consistencia y secuencia): los estados de una cuenta o de un
    lote pertenecen a su conjunto definido, y el paso de la cuenta es una
    transicion de la Tabla 58."""
    conjuntos = {"CUENTA": ESTADOS_CUENTA, "LOTE": ESTADOS_LOTE}
    conjunto = conjuntos.get(evento.tipo_agregado)
    if conjunto is None:
        return
    fuera = [e for e in (evento.estado_previo, evento.estado_nuevo) if e and e not in conjunto]
    if fuera:
        raise ErrorTransicionNoDefinida(
            f"{evento.tipo_evento}: estado fuera del conjunto definido: {', '.join(fuera)}."
        )
    if (
        evento.tipo_agregado == "CUENTA"
        and evento.estado_previo
        and evento.estado_nuevo
        and evento.tipo_evento not in _EVENTOS_COMPENSATORIOS
        and not transicion_definida(evento.estado_previo, evento.estado_nuevo)
    ):
        raise ErrorTransicionNoDefinida(
            f"{evento.tipo_evento}: {evento.estado_previo} -> {evento.estado_nuevo} no es una "
            "transicion de la Tabla 58."
        )


class RegistroEventosSql(RegistroEventos):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def _siguiente_version_y_hash_previo(
        self, tipo_agregado: str, agregado_id: int
    ) -> tuple[int, str]:
        fila = (
            await self._sesion.execute(
                sa.select(EventoModelo.version, EventoModelo.hash_evento)
                .where(
                    EventoModelo.tipo_agregado == tipo_agregado,
                    EventoModelo.agregado_id == agregado_id,
                )
                .order_by(EventoModelo.version.desc())
                .limit(1)
                .with_for_update()
            )
        ).first()
        if fila is None:
            return 1, GENESIS
        return fila.version + 1, fila.hash_evento

    async def _ultimo_estado(self, tipo_agregado: str, agregado_id: int) -> str | None:
        return (
            await self._sesion.execute(
                sa.select(EventoModelo.estado_nuevo)
                .where(
                    EventoModelo.tipo_agregado == tipo_agregado,
                    EventoModelo.agregado_id == agregado_id,
                    EventoModelo.estado_nuevo.is_not(None),
                )
                .order_by(EventoModelo.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _exigir_continuidad(self, evento: Evento) -> None:
        """Tabla 69 ("continuidad"): un evento de transicion parte del
        ultimo estado registrado del agregado. Si el agregado aun no tiene
        un estado registrado no hay contra que comparar."""
        if evento.estado_previo is None:
            return
        ultimo = await self._ultimo_estado(evento.tipo_agregado, evento.agregado_id)
        if ultimo is not None and ultimo != evento.estado_previo:
            raise ErrorContinuidadEstados(
                f"{evento.tipo_evento}: el estado previo {evento.estado_previo!r} no es el "
                f"ultimo estado registrado del agregado ({ultimo!r})."
            )

    async def registrar(self, evento: Evento) -> None:
        _exigir_estados_definidos(evento)
        await self._exigir_continuidad(evento)
        version, hash_anterior = await self._siguiente_version_y_hash_previo(
            evento.tipo_agregado, evento.agregado_id
        )
        ocurrido_en = datetime.now(UTC)
        clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
        hash_evento = calcular_hash_evento(
            clave,
            hash_anterior,
            DatosEventoParaHash(
                tipo_agregado=evento.tipo_agregado,
                agregado_id=evento.agregado_id,
                version=version,
                tipo_evento=evento.tipo_evento,
                actor=evento.actor,
                estado_previo=evento.estado_previo,
                estado_nuevo=evento.estado_nuevo,
                ocurrido_en=ocurrido_en,
            ),
        )
        self._sesion.add(
            EventoModelo(
                tipo_agregado=evento.tipo_agregado,
                agregado_id=evento.agregado_id,
                version=version,
                cuenta_medica_id=evento.cuenta_medica_id,
                tipo_evento=evento.tipo_evento,
                actor=evento.actor,
                estado_previo=evento.estado_previo,
                estado_nuevo=evento.estado_nuevo,
                datos=evento.datos,
                usuario_origen=evento.usuario_origen,
                ocurrido_en=ocurrido_en,
                hash_evento=hash_evento,
            )
        )
        # RNF-04 y AD-04: la proyeccion de lectura del panel se actualiza en
        # la misma transaccion que el evento.
        if evento.tipo_agregado == "CUENTA":
            await aplicar_evento_a_proyeccion(
                self._sesion,
                EventoProyectable(
                    evento.agregado_id,
                    version,
                    evento.tipo_evento,
                    evento.estado_nuevo,
                    ocurrido_en,
                ),
            )
        await self._sesion.commit()
