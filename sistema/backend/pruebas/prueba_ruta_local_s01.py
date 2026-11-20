"""La ruta del `.S01` se resuelve segun el proceso que la lee: el robot con
ventana corre fuera de Docker y guarda su propia ruta de Windows."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.compartido.rutas import ruta_local_s01

_NOMBRE = "937_20690951848_15995250_99553_0000379_202609_20261119.S01"


def prueba_una_ruta_que_existe_se_usa_tal_cual(tmp_path: Path) -> None:
    archivo = tmp_path / _NOMBRE
    archivo.write_bytes(b"contenido")

    assert ruta_local_s01(str(archivo)) == archivo


@pytest.mark.parametrize(
    "guardada",
    [
        "C:\\Users\\clinica\\PROYECTO\\artefactos_s01\\" + _NOMBRE,
        "/otra_carpeta/artefactos_s01/" + _NOMBRE,
    ],
)
def prueba_una_ruta_de_otro_proceso_se_busca_en_la_carpeta_propia(
    guardada: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUTA_ARTEFACTOS_S01", str(tmp_path))

    assert ruta_local_s01(guardada) == tmp_path / _NOMBRE
