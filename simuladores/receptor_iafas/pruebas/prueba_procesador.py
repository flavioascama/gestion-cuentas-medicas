"""Pruebas del procesador simple (Seccion 9.2, Seccion 9.3): construye
ZIPs cifrados sinteticos en memoria (nunca contra un lote real del backend
-- Regla 0.5) y verifica que aceptacion y rechazo respondan a las
verificaciones descritas, incluyendo el descifrado con la contrasena de
la IAFAS."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pyzipper

from app.longitudes_registro import LONGITUDES_REGISTRO
from app.procesador import procesar_lote

_NOMBRE_S01 = "937_20100121809_00140456_20002_1234567_201606_20130605.S01"
_COMPONENTES = {
    "ruc": "20100121809",
    "ipress": "00140456",
    "iafas": "20002",
    "lote": "1234567",
    "periodo": "201606",
    "fecha": "20130605",
}
_CONTRASENA = "clave-de-prueba-iafas-20002"
_CLAVES_IAFAS = {"20002": _CONTRASENA}


def _nombre_interno(prefijo: str) -> str:
    c = _COMPONENTES
    return (
        f"{prefijo}_{c['ruc']}_{c['ipress']}_{c['iafas']}_"
        f"{c['lote']}_{c['periodo']}_{c['fecha']}.txt"
    )


def _zip_cifrado(tmp_path: Path, contrasena: str, longitudes: dict[str, int] | None = None) -> Path:
    longitudes = longitudes or LONGITUDES_REGISTRO
    ruta = tmp_path / _NOMBRE_S01
    with pyzipper.AESZipFile(
        ruta, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zip_archivo:
        zip_archivo.setpassword(contrasena.encode("utf-8"))
        for prefijo, longitud in longitudes.items():
            linea = "X" * longitud
            zip_archivo.writestr(_nombre_interno(prefijo), (linea + "\r\n").encode("ascii"))
    return ruta


def prueba_acepta_un_lote_bien_formado_y_correctamente_cifrado(tmp_path: Path) -> None:
    ruta = _zip_cifrado(tmp_path, _CONTRASENA)
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "ACEPTADO"
    assert resultado.numero_lote == "1234567"
    assert resultado.codigo_iafas == "20002"


def prueba_rechaza_nombre_que_no_cumple_el_patron(tmp_path: Path) -> None:
    ruta = tmp_path / "archivo_cualquiera.S01"
    ruta.write_bytes(b"contenido")
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "patron normado" in (resultado.motivo or "")


def prueba_rechaza_archivo_que_no_es_zip(tmp_path: Path) -> None:
    ruta = tmp_path / _NOMBRE_S01
    ruta.write_bytes(b"esto no es un zip")
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "ZIP valido" in (resultado.motivo or "")


def prueba_rechaza_zip_sin_cifrar(tmp_path: Path) -> None:
    ruta = tmp_path / _NOMBRE_S01
    with zipfile.ZipFile(ruta, "w", compression=zipfile.ZIP_DEFLATED) as zip_archivo:
        for prefijo, longitud in LONGITUDES_REGISTRO.items():
            zip_archivo.writestr(
                _nombre_interno(prefijo), (("X" * longitud) + "\r\n").encode("ascii")
            )
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "no cifrado" in (resultado.motivo or "")


def prueba_rechaza_contrasena_de_descifrado_invalida(tmp_path: Path) -> None:
    ruta = _zip_cifrado(tmp_path, "contrasena-equivocada")
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "descifrado" in (resultado.motivo or "")


def prueba_rechaza_cuando_no_hay_contrasena_para_esa_iafas(tmp_path: Path) -> None:
    ruta = _zip_cifrado(tmp_path, _CONTRASENA)
    resultado = procesar_lote(ruta, claves_iafas={})
    assert resultado.estado == "RECHAZADO"
    assert "descifrado" in (resultado.motivo or "")


def prueba_rechaza_zip_al_que_le_falta_una_tabla(tmp_path: Path) -> None:
    incompleto = {p: n for i, (p, n) in enumerate(LONGITUDES_REGISTRO.items()) if i > 0}
    ruta = _zip_cifrado(tmp_path, _CONTRASENA, longitudes=incompleto)
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "Faltan archivos" in (resultado.motivo or "")


def prueba_rechaza_una_linea_con_longitud_incorrecta(tmp_path: Path) -> None:
    ruta = tmp_path / _NOMBRE_S01
    with pyzipper.AESZipFile(
        ruta, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zip_archivo:
        zip_archivo.setpassword(_CONTRASENA.encode("utf-8"))
        for prefijo, longitud in LONGITUDES_REGISTRO.items():
            longitud_real = longitud if prefijo != "date" else longitud - 1
            linea = "X" * longitud_real
            zip_archivo.writestr(_nombre_interno(prefijo), (linea + "\r\n").encode("ascii"))
    resultado = procesar_lote(ruta, _CLAVES_IAFAS)
    assert resultado.estado == "RECHAZADO"
    assert "date" in (resultado.motivo or "")
