"""Archivo Excel que el administrador envia para cargar una version nueva de
un catalogo (CPMS o GTIN): llega en JSON, con el contenido en base64, igual
que el `.S01` del registro manual de la validacion (sin multipart)."""

from __future__ import annotations

import base64
import binascii


class ErrorArchivoCatalogoInvalido(Exception):
    """El archivo no sirve para cargar el catalogo; el mensaje dice por que."""


def decodificar_xlsx(nombre: str, contenido_base64: str) -> bytes:
    if not nombre.lower().endswith(".xlsx"):
        raise ErrorArchivoCatalogoInvalido("El archivo debe ser un Excel .xlsx.")
    if len(nombre) > 100:
        raise ErrorArchivoCatalogoInvalido("El nombre del archivo pasa de 100 caracteres.")
    try:
        contenido = base64.b64decode(contenido_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ErrorArchivoCatalogoInvalido("No se pudo leer el archivo.") from error
    if not contenido:
        raise ErrorArchivoCatalogoInvalido("El archivo está vacío.")
    return contenido
