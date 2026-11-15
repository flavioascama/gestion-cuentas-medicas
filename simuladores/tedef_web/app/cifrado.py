"""Cifrado del .S01 (Seccion 9.2: "ZIP cifrado con la contrasena de la
IAFAS... con la biblioteca pyzipper (AES). El algoritmo real no es
publico" -- supuesto 1 de la Seccion 16 del plan)."""

from __future__ import annotations

import io

import pyzipper


def cifrar_archivos(archivos: dict[str, bytes], contrasena: str) -> bytes:
    """`archivos`: {nombre_interno_del_txt: contenido}. Devuelve el .S01
    (ZIP cifrado con AES) como bytes."""

    buffer = io.BytesIO()
    with pyzipper.AESZipFile(
        buffer, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as paquete:
        paquete.setpassword(contrasena.encode("utf-8"))
        for nombre, contenido in archivos.items():
            paquete.writestr(nombre, contenido)
    return buffer.getvalue()
