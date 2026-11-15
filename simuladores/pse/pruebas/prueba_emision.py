from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.almacenamiento import AlmacenamientoPse
from app.portal_web import construir_app


def _cliente(tmp_path: Path) -> TestClient:
    almacenamiento = AlmacenamientoPse(tmp_path / "pse.sqlite3")
    return TestClient(construir_app(almacenamiento))


def prueba_emitir_comprobante_devuelve_datos_validos(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post(
        "/comprobantes", json={"ruc_ipress": "20123456789", "codigo_ipress": "15995250"}
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["tipo_documento_pago"] == "01"
    assert cuerpo["serie"] == "E001"
    assert cuerpo["numero"] == "00000001"
    assert cuerpo["fecha_emision"]


def prueba_cada_emision_incrementa_el_numero(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)
    primera = cliente.post(
        "/comprobantes", json={"ruc_ipress": "20123456789", "codigo_ipress": "15995250"}
    )
    segunda = cliente.post(
        "/comprobantes", json={"ruc_ipress": "20123456789", "codigo_ipress": "15995250"}
    )
    assert primera.json()["numero"] == "00000001"
    assert segunda.json()["numero"] == "00000002"
