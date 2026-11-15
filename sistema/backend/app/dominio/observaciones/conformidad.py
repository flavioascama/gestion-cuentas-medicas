"""CU-07 (Registrar el resultado de la auditoria): la conformidad de la
IAFAS sin observaciones. El otro resultado posible, la observacion, es
CU-08 (`RegistrarObservacion`).

La conformidad no es un estado de la Tabla 58 (el conjunto de estados es
cerrado): la cuenta sigue en auditoria hasta que la IAFAS liquida. Se
registra como evento de la cuenta, cierra el control del plazo de
comunicacion del resultado (hito 3 de la Tabla 61) y deja la cuenta
derivada a liquidacion. Vale para la auditoria en curso: si la cuenta
vuelve a auditoria despues (por ejemplo, tras una subsanacion), la
conformidad anterior ya no cuenta."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos

TIPO_EVENTO_CONFORMIDAD = "AUDITORIA_CONFORME"
ESTADOS_EN_AUDITORIA = frozenset({"EN_AUDITORIA", "SUBSANADA"})


class ErrorCuentaInexistenteAuditoria(Exception):
    pass


class ErrorCuentaSinAuditoriaEnCurso(Exception):
    pass


class ErrorConformidadYaRegistrada(Exception):
    pass


class RepositorioConformidadAuditoria(Protocol):
    async def conformidad_vigente(self, cuenta_medica_id: int) -> datetime | None:
        """Cuando se registro la conformidad de la auditoria en curso, o
        None si no hay una (la cuenta entro a su estado actual despues)."""
        ...


class RegistrarConformidadAuditoria:
    def __init__(
        self,
        estado_cuenta: RepositorioEstadoCuenta,
        conformidades: RepositorioConformidadAuditoria,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._estado_cuenta = estado_cuenta
        self._conformidades = conformidades
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_medica_id: int, actor: str) -> None:
        estado = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if estado is None:
            raise ErrorCuentaInexistenteAuditoria(f"No existe la cuenta {cuenta_medica_id}.")
        if estado not in ESTADOS_EN_AUDITORIA:
            raise ErrorCuentaSinAuditoriaEnCurso(
                f"La cuenta {cuenta_medica_id} esta en estado {estado!r}: no tiene una "
                "auditoria en curso."
            )
        if await self._conformidades.conformidad_vigente(cuenta_medica_id) is not None:
            raise ErrorConformidadYaRegistrada(
                f"La conformidad de la auditoria de la cuenta {cuenta_medica_id} ya esta "
                "registrada."
            )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_CONFORMIDAD,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"estado_cuenta": estado},
            )
        )


class ConsultarConformidadAuditoria:
    def __init__(self, conformidades: RepositorioConformidadAuditoria) -> None:
        self._conformidades = conformidades

    async def ejecutar(self, cuenta_medica_id: int) -> datetime | None:
        return await self._conformidades.conformidad_vigente(cuenta_medica_id)
