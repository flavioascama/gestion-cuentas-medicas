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


def prueba_emitir_nota_da_serie_y_numero_segun_el_tipo(tmp_path: Path) -> None:
    cliente = _cliente(tmp_path)
    datos = {"ruc_ipress": "20123456789", "codigo_ipress": "15995250"}
    credito = cliente.post("/notas", json={**datos, "tipo": "C"})
    otra = cliente.post("/notas", json={**datos, "tipo": "C"})
    debito = cliente.post("/notas", json={**datos, "tipo": "D"})
    assert credito.status_code == 201, credito.text
    assert (credito.json()["serie"], credito.json()["numero"]) == ("EC01", "00000001")
    assert otra.json()["numero"] == "00000002"
    assert (debito.json()["serie"], debito.json()["numero"]) == ("ED01", "00000001")
    assert credito.json()["fecha_emision"]


def prueba_emitir_nota_rechaza_un_tipo_desconocido(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post(
        "/notas", json={"ruc_ipress": "20123456789", "codigo_ipress": "15995250", "tipo": "N"}
    )
    assert respuesta.status_code == 422


_DATOS = {"ruc_ipress": "20123456789", "codigo_ipress": "15995250"}
_CLIENTE_Y_MONTOS = {
    "tipo_comprobante": "01",
    "codigo_cliente": "19395",
    "razon_social_cliente": "IAFAS de prueba",
    "valor_venta": "100.00",
    "igv": "18.00",
    "total": "118.00",
}


def prueba_emitir_acepta_cliente_y_montos_que_cuadran(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post("/comprobantes", json={**_DATOS, **_CLIENTE_Y_MONTOS})
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["tipo_documento_pago"] == "01"


def prueba_emitir_rechaza_un_total_que_no_cuadra(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post(
        "/comprobantes", json={**_DATOS, **_CLIENTE_Y_MONTOS, "total": "120.00"}
    )
    assert respuesta.status_code == 422


def prueba_emitir_rechaza_montos_negativos(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post(
        "/comprobantes",
        json={**_DATOS, **_CLIENTE_Y_MONTOS, "valor_venta": "-1.00", "total": "17.00"},
    )
    assert respuesta.status_code == 422


def prueba_emitir_nota_acepta_monto_y_comprobante_referido(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post(
        "/notas",
        json={
            **_DATOS,
            "tipo": "C",
            "monto": "50.00",
            "comprobante_referido": {"tipo_comprobante": "01", "serie": "E001", "numero": "7"},
        },
    )
    assert respuesta.status_code == 201, respuesta.text


def prueba_emitir_nota_rechaza_un_monto_negativo(tmp_path: Path) -> None:
    respuesta = _cliente(tmp_path).post("/notas", json={**_DATOS, "tipo": "C", "monto": "-5"})
    assert respuesta.status_code == 422
