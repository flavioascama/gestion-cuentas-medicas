"""Custodia cifrada de las evidencias del robot (C-12, RNF-16): la captura
del documento de acreditacion, sus metadatos y la traza de Playwright se
guardan cifrados con Fernet, con una clave propia (CLAVE_CIFRADO_EVIDENCIAS,
distinta de la de las sesiones asistidas). Ningun archivo de evidencia
toca el disco sin cifrar; solo `trabajador.descifrar_evidencia` los abre,
y deja el acceso registrado en el historial de la cuenta."""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

SUFIJO_CIFRADO = ".cifrado"


class ErrorCifradoEvidencia(Exception):
    pass


class AlmacenEvidenciasCifrado:
    def __init__(self, raiz: Path, clave: str) -> None:
        self._raiz = raiz
        self._fernet = Fernet(clave.encode("utf-8"))

    @property
    def raiz(self) -> Path:
        return self._raiz

    def guardar(self, relativa: str, contenido: bytes) -> str:
        """Guarda `contenido` cifrado en `<raiz>/<relativa>.cifrado` y
        devuelve esa ruta relativa."""
        cifrada = relativa + SUFIJO_CIFRADO
        destino = self._raiz / cifrada
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(self._fernet.encrypt(contenido))
        return cifrada

    def leer(self, relativa_cifrada: str) -> bytes:
        try:
            return self._fernet.decrypt((self._raiz / relativa_cifrada).read_bytes())
        except InvalidToken as error:
            raise ErrorCifradoEvidencia(
                f"No se pudo descifrar {relativa_cifrada}: clave incorrecta o archivo alterado."
            ) from error

    def cifrar_existente(self, archivo: Path) -> Path:
        """Cifra un archivo de evidencia guardado antes en claro y borra el
        original."""
        destino = archivo.with_name(archivo.name + SUFIJO_CIFRADO)
        destino.write_bytes(self._fernet.encrypt(archivo.read_bytes()))
        archivo.unlink()
        return destino
