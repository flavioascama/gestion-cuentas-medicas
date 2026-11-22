"""Correccion de los nombres y apellidos del asegurado (auditoria final,
hallazgo 8): el analista los corrige desde el detalle de la cuenta mientras
esta siga Registrada. El documento no se corrige. El evento no lleva los
nombres: son datos personales y no van en el historial."""

from __future__ import annotations

from typing import Protocol

from app.compartido.nombres_estados import nombre_estado
from app.dominio.integracion.casos_uso_ingesta import (
    MENSAJE_NOMBRES_EN_BLANCO,
    nombres_recortados,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos

TIPO_EVENTO_ASEGURADO_CORREGIDO = "ASEGURADO_CORREGIDO"
ESTADO_CORREGIBLE = "REGISTRADA"
# Los nombres son de la persona y los comparten todas sus cuentas: no cambian
# si alguna ya salio de la clinica (cualquier estado fuera de estos dos).
ESTADOS_SIN_SALIDA = frozenset({"REGISTRADA", "ANULADA"})


class ErrorCorreccionAsegurado(Exception):
    """Base de los errores de este caso de uso."""


class ErrorCuentaInexistenteAsegurado(ErrorCorreccionAsegurado):
    pass


class ErrorAseguradoNoCorregible(ErrorCorreccionAsegurado):
    pass


class ErrorNombresAseguradoInvalidos(ErrorCorreccionAsegurado):
    pass


class ErrorAseguradoConCuentasAvanzadas(ErrorCorreccionAsegurado):
    pass


class RepositorioCorreccionAsegurado(Protocol):
    async def estado_cuenta(self, cuenta_id: int) -> str | None:
        """Estado de la cuenta; None si no existe."""
        ...

    async def asegurado_con_otras_cuentas_avanzadas(self, cuenta_id: int) -> bool:
        """El asegurado de la cuenta tiene otra en un estado fuera de ESTADOS_SIN_SALIDA."""
        ...

    async def corregir_nombres(self, cuenta_id: int, nombres: str, apellidos: str) -> None:
        """Reemplaza los nombres y apellidos del asegurado de la cuenta."""
        ...


class CorregirNombresAsegurado:
    def __init__(
        self, repositorio: RepositorioCorreccionAsegurado, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_id: int, nombres: str, apellidos: str, actor: str) -> None:
        estado = await self._repositorio.estado_cuenta(cuenta_id)
        if estado is None:
            raise ErrorCuentaInexistenteAsegurado("No existe la cuenta.")
        if estado != ESTADO_CORREGIBLE:
            raise ErrorAseguradoNoCorregible(
                f"La cuenta está en estado {nombre_estado(estado)}: los nombres del asegurado "
                f"solo se corrigen mientras la cuenta está {nombre_estado(ESTADO_CORREGIBLE)}."
            )
        if await self._repositorio.asegurado_con_otras_cuentas_avanzadas(cuenta_id):
            raise ErrorAseguradoConCuentasAvanzadas(
                "El asegurado tiene cuentas ya facturadas o enviadas: sus nombres no se pueden "
                "corregir."
            )
        recortados = nombres_recortados(nombres, apellidos)
        if recortados is None:
            raise ErrorNombresAseguradoInvalidos(MENSAJE_NOMBRES_EN_BLANCO)
        await self._repositorio.corregir_nombres(cuenta_id, *recortados)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento=TIPO_EVENTO_ASEGURADO_CORREGIDO,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={},
            )
        )
