"""Modo de falla inducida (Seccion 9.1): activable por variable de entorno
al arrancar, o por una ruta de administracion en caliente. Estado en
memoria del propio proceso -- un simulador de pruebas deterministas no
necesita persistirlo entre reinicios."""

from __future__ import annotations

MODOS_VALIDOS = ("ninguno", "caida_servicio", "expiracion_sesion", "respuesta_vacia")


class EstadoFalla:
    def __init__(self, modo_inicial: str) -> None:
        if modo_inicial not in MODOS_VALIDOS:
            raise ValueError(f"Modo de falla invalido: {modo_inicial!r}")
        self._modo = modo_inicial

    @property
    def modo(self) -> str:
        return self._modo

    def fijar(self, modo: str) -> None:
        if modo not in MODOS_VALIDOS:
            raise ValueError(f"Modo de falla invalido: {modo!r}")
        self._modo = modo
