"""Pruebas de AlmacenSesionesCifrado (Seccion 8.4, punto 4: "guarda el
estado de sesion de Playwright... cifrado en el volumen
sesiones_plataformas")."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from trabajador.soporte.cifrado import AlmacenSesionesCifrado, ErrorCifradoSesion

_CLAVE = Fernet.generate_key().decode()


def prueba_cargar_sin_archivo_devuelve_none(tmp_path: Path) -> None:
    almacen = AlmacenSesionesCifrado(tmp_path, _CLAVE)
    assert almacen.cargar("acredita_salud") is None


def prueba_guardar_y_cargar_recupera_el_mismo_estado(tmp_path: Path) -> None:
    almacen = AlmacenSesionesCifrado(tmp_path, _CLAVE)
    estado = {"cookies": [{"name": "sesion", "value": "abc123"}], "origins": []}

    almacen.guardar("acredita_salud", estado)

    assert almacen.cargar("acredita_salud") == estado


def prueba_el_archivo_en_disco_no_es_json_plano(tmp_path: Path) -> None:
    almacen = AlmacenSesionesCifrado(tmp_path, _CLAVE)
    almacen.guardar(
        "acredita_salud", {"cookies": [{"name": "secreta", "value": "no-deberia-verse"}]}
    )

    contenido = (tmp_path / "storage_state_acredita_salud.enc").read_bytes()
    assert b"no-deberia-verse" not in contenido


def prueba_cada_plataforma_tiene_su_propio_archivo(tmp_path: Path) -> None:
    almacen = AlmacenSesionesCifrado(tmp_path, _CLAVE)
    almacen.guardar("acredita_salud", {"cookies": [], "origins": [], "id": 1})
    almacen.guardar("tedef_web", {"cookies": [], "origins": [], "id": 2})

    assert almacen.cargar("acredita_salud") == {"cookies": [], "origins": [], "id": 1}
    assert almacen.cargar("tedef_web") == {"cookies": [], "origins": [], "id": 2}


def prueba_clave_incorrecta_no_descifra(tmp_path: Path) -> None:
    almacen = AlmacenSesionesCifrado(tmp_path, _CLAVE)
    almacen.guardar("acredita_salud", {"cookies": []})

    otra_clave = Fernet.generate_key().decode()
    otro_almacen = AlmacenSesionesCifrado(tmp_path, otra_clave)
    with pytest.raises(ErrorCifradoSesion):
        otro_almacen.cargar("acredita_salud")
