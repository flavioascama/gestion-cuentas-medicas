"""Lectura de las evidencias del robot, cifradas con Fernet (C-12,
RNF-16) con la clave propia de las evidencias (CLAVE_CIFRADO_EVIDENCIAS):
el trabajador las escribe en la carpeta de reportes y el servidor solo las
lee, sin dejarlas en claro en el disco."""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.dominio.acreditacion.solicitud_atencion import (
    AlmacenEvidencias,
    ErrorSolicitudAtencionNoDisponible,
)


class AlmacenEvidenciasCifrado(AlmacenEvidencias):
    def __init__(self, raiz: Path, clave: str) -> None:
        self._raiz = raiz.resolve()
        self._clave = clave

    def leer(self, ruta: str) -> bytes:
        archivo = (self._raiz / ruta).resolve()
        if not archivo.is_relative_to(self._raiz) or not archivo.is_file():
            raise ErrorSolicitudAtencionNoDisponible("El documento no esta disponible.")
        if not self._clave:
            raise ErrorSolicitudAtencionNoDisponible("Falta la clave de las evidencias.")
        try:
            return Fernet(self._clave.encode("utf-8")).decrypt(archivo.read_bytes())
        except (InvalidToken, ValueError) as error:
            raise ErrorSolicitudAtencionNoDisponible(
                "El documento no se pudo descifrar."
            ) from error
