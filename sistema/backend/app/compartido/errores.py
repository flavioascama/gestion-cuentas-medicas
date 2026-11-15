"""Formato uniforme de error de la API (Seccion 10.1): codigo, mensaje, detalles."""

from __future__ import annotations

from typing import Any


class ErrorAplicacion(Exception):
    """Excepcion base de errores de negocio, traducida a respuesta HTTP uniforme."""

    def __init__(
        self,
        codigo: str,
        mensaje: str,
        estado_http: int = 400,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado_http = estado_http
        self.detalles = detalles or {}

    def cuerpo_respuesta(self) -> dict[str, Any]:
        return {"codigo": self.codigo, "mensaje": self.mensaje, "detalles": self.detalles}
