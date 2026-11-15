"""Cifrado en reposo de las columnas sensibles (C-05, RNF-16, Ley 29733 art.
16): la identidad del asegurado (nombres, apellidos, numero de documento)
y los datos clinicos de la cuenta (historia clinica, diagnostico) se
guardan cifrados con Fernet (AES-128-CBC con HMAC-SHA256) y la clave
CLAVE_CIFRADO_DATOS, que vive fuera de la base.

El cifrado es transparente para el resto del sistema: se cifra al escribir
y se descifra al leer. Como Fernet no es determinista, la busqueda por
documento usa un indice ciego (HMAC-SHA256 del tipo y el numero) en vez de
la columna cifrada."""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from typing import Any

import sqlalchemy as sa
from cryptography.fernet import Fernet
from sqlalchemy.types import TypeDecorator

from app.compartido.configuracion import obtener_configuracion

LONGITUD_COLUMNA_CIFRADA = 500


@lru_cache
def _fernet(clave: str) -> Fernet:
    return Fernet(clave.encode("utf-8"))


@lru_cache
def _clave_indice(clave: str) -> bytes:
    # Clave propia del indice, derivada de la de cifrado: el mismo secreto
    # no se usa para dos fines distintos.
    return hashlib.sha256(b"indice-ciego:" + clave.encode("utf-8")).digest()


def cifrar_texto(valor: str, clave: str | None = None) -> str:
    clave = clave or obtener_configuracion().clave_cifrado_datos
    return _fernet(clave).encrypt(valor.encode("utf-8")).decode("ascii")


def descifrar_texto(valor: str, clave: str | None = None) -> str:
    clave = clave or obtener_configuracion().clave_cifrado_datos
    return _fernet(clave).decrypt(valor.encode("ascii")).decode("utf-8")


def indice_ciego(*partes: str, clave: str | None = None) -> str:
    clave = clave or obtener_configuracion().clave_cifrado_datos
    mensaje = "\x1f".join(partes).encode("utf-8")
    return hmac.new(_clave_indice(clave), mensaje, hashlib.sha256).hexdigest()


class TextoCifrado(TypeDecorator[str]):
    """Columna de texto que se guarda cifrada."""

    impl = sa.String(LONGITUD_COLUMNA_CIFRADA)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else cifrar_texto(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else descifrar_texto(str(value))
