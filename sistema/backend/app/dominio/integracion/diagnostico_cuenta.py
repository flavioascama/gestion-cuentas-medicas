"""Registrar el diagnostico principal de una cuenta despues de crearla
(2026-11-18).

Al registrar la cuenta el diagnostico es opcional, porque en la admision no
siempre se conoce; pero el estandar TEDEF lo exige (T2, campo 18). Antes no
habia forma de completarlo: una cuenta sin diagnostico llegaba a FACTURADA y
su lote nunca salia conforme. Ahora se puede registrar, y la cuenta no pasa a
FACTURADA sin el (ConsultarCompletitudCuenta)."""

from __future__ import annotations

from typing import Protocol

from app.compartido.nombres_estados import nombre_estado
from app.dominio.orquestacion.correccion_validador import admite_correccion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos

TIPO_EVENTO_DIAGNOSTICO_REGISTRADO = "DIAGNOSTICO_REGISTRADO"
# Antes de facturar y al corregir una cuenta rechazada se puede cambiar. En
# una cuenta ya facturada solo se completa si faltaba: esas cuentas no
# pueden estar en un lote, porque sin diagnostico el lote no sale conforme.
# La excepcion es la cuenta cuyo lote observo el validador (admite_correccion).
_ESTADOS_EDITABLES = frozenset({"REGISTRADA", "RECHAZADA"})
_ESTADO_SOLO_COMPLETAR = "FACTURADA"


class ErrorDiagnostico(Exception):
    """Base de los errores de este caso de uso."""


class ErrorCuentaInexistenteDiagnostico(ErrorDiagnostico):
    def __init__(self, cuenta_id: int) -> None:
        super().__init__("No existe la cuenta médica.")


class ErrorDiagnosticoNoAdmitido(ErrorDiagnostico):
    def __init__(self, estado: str) -> None:
        super().__init__(
            "El diagnóstico ya no se puede cambiar en una cuenta en estado "
            f"{nombre_estado(estado)}."
        )


class ErrorCie10Inexistente(ErrorDiagnostico):
    def __init__(self, codigo: str) -> None:
        super().__init__(f"El código {codigo} no está en el catálogo CIE-10.")


class RepositorioDiagnosticoCuenta(Protocol):
    async def estado_y_diagnostico(self, cuenta_id: int) -> tuple[str, str | None] | None:
        """(estado, diagnostico actual) de la cuenta; None si no existe."""
        ...

    async def existe_cie10(self, codigo: str) -> bool: ...

    async def fijar_diagnostico(self, cuenta_id: int, codigo: str) -> None: ...


def normalizar_cie10(codigo: str) -> str:
    """El catalogo guarda el codigo sin punto: "J18.9" se acepta como "J189"."""
    return codigo.strip().upper().replace(".", "")


def admite_diagnostico(estado: str, diagnostico_actual: str | None) -> bool:
    if estado in _ESTADOS_EDITABLES:
        return True
    return estado == _ESTADO_SOLO_COMPLETAR and not diagnostico_actual


class RegistrarDiagnosticoPrincipal:
    def __init__(
        self,
        repositorio: RepositorioDiagnosticoCuenta,
        registro_eventos: RegistroEventos,
        estado_cuenta: RepositorioEstadoCuenta,
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos
        self._estado_cuenta = estado_cuenta

    async def ejecutar(self, cuenta_id: int, codigo: str, actor: str) -> str:
        codigo = normalizar_cie10(codigo)
        actual = await self._repositorio.estado_y_diagnostico(cuenta_id)
        if actual is None:
            raise ErrorCuentaInexistenteDiagnostico(cuenta_id)
        estado, diagnostico = actual
        if not await admite_correccion(
            self._estado_cuenta, cuenta_id, admite_diagnostico(estado, diagnostico)
        ):
            raise ErrorDiagnosticoNoAdmitido(estado)
        if not await self._repositorio.existe_cie10(codigo):
            raise ErrorCie10Inexistente(codigo)
        await self._repositorio.fijar_diagnostico(cuenta_id, codigo)
        # Sin el codigo en el evento: el diagnostico es un dato clinico y no
        # va en el historial (control C-11).
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento=TIPO_EVENTO_DIAGNOSTICO_REGISTRADO,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={},
            )
        )
        return codigo
