"""Cifrado del `storage_state` por portal (Seccion 8.4, punto 4: 'guarda
el estado de sesion de Playwright (storage_state) cifrado en el volumen
sesiones_plataformas'). El JSON nunca toca el disco sin cifrar: se pide a
Playwright en memoria (`GestorNavegador.obtener_estado_sesion`, sin ruta)
y se descifra tambien en memoria antes de pasarlo a `nuevo_contexto`."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from playwright.async_api import StorageState


class ErrorCifradoSesion(Exception):
    pass


class AlmacenSesionesCifrado:
    def __init__(self, directorio: Path, clave: str) -> None:
        self._directorio = directorio
        self._fernet = Fernet(clave.encode("utf-8"))

    def _ruta(self, plataforma: str) -> Path:
        return self._directorio / f"storage_state_{plataforma}.enc"

    def cargar(self, plataforma: str) -> StorageState | None:
        ruta = self._ruta(plataforma)
        if not ruta.exists():
            return None
        try:
            contenido = self._fernet.decrypt(ruta.read_bytes())
        except InvalidToken as error:
            raise ErrorCifradoSesion(
                f"No se pudo descifrar el storage_state de {plataforma!r}: clave incorrecta "
                "o archivo corrupto."
            ) from error
        estado: StorageState = json.loads(contenido)
        return estado

    def guardar(self, plataforma: str, estado: StorageState) -> None:
        self._directorio.mkdir(parents=True, exist_ok=True)
        contenido = json.dumps(estado).encode("utf-8")
        self._ruta(plataforma).write_bytes(self._fernet.encrypt(contenido))
