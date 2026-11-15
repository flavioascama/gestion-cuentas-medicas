"""Sesion con expiracion configurable, en tres pasos (Seccion 9.2: ingreso
con CAPTCHA, seleccionar perfil, seleccionar entidad -- recien entonces la
sesion queda activa). Independiente de
simuladores/acredita_salud/app/sesion.py (Regla 0.5): mismo patron, otro
archivo, porque este simulador necesita ademas el estado intermedio de
perfil/entidad.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

NOMBRE_COOKIE = "sesion_tedef_web"

PERFILES_VALIDOS = ("TEDEF-Supervisor-IPRESS", "TEDEF-Validador-IPRESS")


@dataclass(frozen=True, slots=True)
class Sesion:
    token: str
    usuario: str
    expira_en: datetime
    perfil: str | None = None
    entidad_seleccionada: bool = False

    @property
    def activa(self) -> bool:
        return self.perfil is not None and self.entidad_seleccionada


class ErrorSesionInvalida(Exception):
    """Sin sesion vigente: sin cookie, token desconocido o expirada."""


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

    def seleccionar_perfil(self, token: str, perfil: str) -> Sesion:
        if perfil not in PERFILES_VALIDOS:
            raise ValueError(f"Perfil invalido: {perfil!r}")
        sesion = replace(self._sesiones[token], perfil=perfil)
        self._sesiones[token] = sesion
        return sesion

    def seleccionar_entidad(self, token: str) -> Sesion:
        sesion = replace(self._sesiones[token], entidad_seleccionada=True)
        self._sesiones[token] = sesion
        return sesion

    def cerrar(self, token: str) -> None:
        self._sesiones.pop(token, None)
