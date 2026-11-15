"""Sesion con expiracion configurable (Seccion 9.1, pantalla de ingreso).

El robot de la Fase 11 tiene que poder detectar una sesion vencida y
reautenticar (Seccion 8.1: 'antes de cada consulta verifica que la sesion
siga vigente y reautentica si expiro'), asi que la expiracion tiene que
ser real, no solo cosmetica: pasado `expira_en`, la sesion deja de
aceptarse aunque el token exista.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

NOMBRE_COOKIE = "sesion_acredita_salud"


@dataclass(frozen=True, slots=True)
class Sesion:
    token: str
    usuario: str
    expira_en: datetime


class ErrorSesionInvalida(Exception):
    """Sin sesion vigente: sin cookie, token desconocido, expirada, o el
    modo de falla 'expiracion_sesion' fuerza el rechazo (Seccion 9.1)."""


class GestorSesiones:
    def __init__(self, duracion_minutos: int) -> None:
        self._duracion = timedelta(minutes=duracion_minutos)
        self._sesiones: dict[str, Sesion] = {}

    def iniciar(self, usuario: str) -> Sesion:
        token = secrets.token_urlsafe(24)
        sesion = Sesion(token=token, usuario=usuario, expira_en=datetime.now() + self._duracion)
        self._sesiones[token] = sesion
        return sesion

    def validar(self, token: str | None) -> Sesion | None:
        if token is None:
            return None
        sesion = self._sesiones.get(token)
        if sesion is None:
            return None
        if datetime.now() > sesion.expira_en:
            del self._sesiones[token]
            return None
        return sesion

    def cerrar(self, token: str) -> None:
        self._sesiones.pop(token, None)
