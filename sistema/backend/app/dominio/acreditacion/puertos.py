"""Puertos del contexto de acreditacion (Seccion 5.2, 8.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion, ResultadoAcreditacion


class ErrorAcreditacion(Exception):
    pass


class ErrorCuentaNoEncontrada(ErrorAcreditacion):
    pass


class AcreditacionWeb(Protocol):
    """Puerto sobre el robot RPA (Seccion 8.1, Seccion 14 supuesto 12:
    nombrado por funcion, nunca por la marca del portal que simula). La
    unica implementacion vive en sistema/automatizacion/trabajador/robots/,
    un proceso separado (AD-02) que usa Playwright -- el dominio no lo
    sabe, solo pide 'verificar la cobertura de este contexto' y espera un
    ResultadoAcreditacion."""

    async def verificar_cobertura(
        self, contexto: ContextoCuentaAcreditacion, trabajo_id: int
    ) -> ResultadoAcreditacion:
        """`trabajo_id` identifica la carpeta de evidencia
        (reportes/evidencia_acreditacion/<trabajo_id>/, Seccion 8.1), no
        se usa para nada mas."""
        ...


class RepositorioAcreditacion(Protocol):
    async def obtener_contexto_cuenta(
        self, cuenta_medica_id: int
    ) -> ContextoCuentaAcreditacion | None:
        """None si la cuenta no existe."""
        ...

    async def existe_acreditacion(self, cuenta_medica_id: int) -> bool:
        """Seccion 8.1: 'idempotencia: un reintento no duplica
        registros' -- `acreditacion.cuenta_id` es unica (Fase 7)."""
        ...

    async def guardar_acreditacion(
        self,
        cuenta_medica_id: int,
        resultado: ResultadoAcreditacion,
        instante: datetime,
        duracion_ms: int,
        componente_ejecutor: str,
    ) -> int:
        """Devuelve el id de la fila creada en `acreditacion`."""
        ...

    async def obtener_acreditacion(self, cuenta_medica_id: int) -> AcreditacionRegistrada | None:
        """None si la cuenta no tiene acreditacion registrada (Fase 18,
        `GET /cuentas/{id}/acreditacion`)."""
        ...


@dataclass(frozen=True, slots=True)
class AcreditacionRegistrada:
    """Lo que devuelve `obtener_acreditacion`: el resultado ya guardado
    mas los datos propios de la fila (`id`, `instante`) que
    `ResultadoAcreditacion` no lleva porque los asigna el repositorio al
    persistir, no el robot que lo produce."""

    id: int
    instante: datetime
    resultado: ResultadoAcreditacion
    # Quien la obtuvo (RF-02): el robot sobre ACREDITA SALUD o el registro
    # manual en modo de contingencia (RF-23); la pantalla lo dice.
    componente_ejecutor: str = ""
