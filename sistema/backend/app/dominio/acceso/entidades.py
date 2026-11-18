"""Entidades del contexto de acceso (Seccion 6.1 y, desde la Fase 25,
Seccion 5.2.3.1): usuario, rol, usuario_rol.

Los seis roles son un conjunto cerrado, tal como los enumera la Tabla 45
de la tesis (actores primarios del sistema). Los cuatro originales del
OE1 (analista, auditor, jefe, administrador) se amplian en la Fase 25,
al implementar el OE2/OE3, con los dos actores primarios que el motor de
orquestacion y el panel gerencial incorporan: personal de tesoreria
(registra liquidaciones y concilia pagos) y gerente administrativo
(visualiza los indicadores del ciclo). RF-19 administra la asignacion de
estos roles a un usuario, no la creacion de roles nuevos: la arquitectura
(AD-06) ya asume un vocabulario de roles fijo y conocido por cada
operacion protegida. Ver docs/DECISIONES.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class NombreRol(StrEnum):
    ANALISTA = "analista"
    AUDITOR = "auditor"
    JEFE = "jefe"
    ADMINISTRADOR = "administrador"
    TESORERIA = "tesoreria"
    GERENTE = "gerente"


@dataclass(frozen=True, slots=True)
class Usuario:
    """Entidad de dominio. `hash_clave` nunca sale de esta capa hacia la API.

    `intentos_fallidos` y `bloqueado_hasta` sostienen el control C-01 de la
    Seccion 5.2.7 de la tesis ("tras cinco intentos fallidos la cuenta se
    bloquea durante quince minutos"): se incrementan y se fijan desde
    `IniciarSesion`, nunca desde la pantalla de administracion de usuarios
    (ver `ActualizarUsuario`, que no los toca).

    `debe_cambiar_clave` (2026-11-18): la clave la puso el administrador y
    la persona todavia no la cambio; hasta que lo haga solo puede cambiarla
    o salir (`app.dominio.acceso.cambio_clave`)."""

    id: int | None
    nombre_usuario: str
    nombres: str
    hash_clave: str
    activo: bool
    roles: frozenset[NombreRol] = field(default_factory=frozenset)
    intentos_fallidos: int = 0
    bloqueado_hasta: datetime | None = None
    debe_cambiar_clave: bool = False

    def tiene_alguno(self, roles: frozenset[NombreRol]) -> bool:
        return bool(self.roles & roles)
