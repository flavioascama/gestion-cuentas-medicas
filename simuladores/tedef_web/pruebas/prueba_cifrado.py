from __future__ import annotations

import io

import pytest
import pyzipper

from app.cifrado import cifrar_archivos

_ARCHIVOS = {"dfac_1.txt": b"X" * 242, "date_1.txt": b"Y" * 410}


def prueba_descifra_con_la_contrasena_correcta() -> None:
    contenido = cifrar_archivos(_ARCHIVOS, "clave-correcta")
    with pyzipper.AESZipFile(io.BytesIO(contenido)) as paquete:
        paquete.setpassword(b"clave-correcta")
        assert paquete.read("dfac_1.txt") == _ARCHIVOS["dfac_1.txt"]
        assert paquete.read("date_1.txt") == _ARCHIVOS["date_1.txt"]


def prueba_rechaza_contrasena_incorrecta() -> None:
    contenido = cifrar_archivos(_ARCHIVOS, "clave-correcta")
    with pyzipper.AESZipFile(io.BytesIO(contenido)) as paquete:
        paquete.setpassword(b"clave-incorrecta")
        with pytest.raises(RuntimeError):
            paquete.read("dfac_1.txt")


def prueba_las_entradas_quedan_marcadas_como_cifradas() -> None:
    contenido = cifrar_archivos(_ARCHIVOS, "clave-correcta")
    with pyzipper.AESZipFile(io.BytesIO(contenido)) as paquete:
        for info in paquete.infolist():
            assert info.flag_bits & 0x1
