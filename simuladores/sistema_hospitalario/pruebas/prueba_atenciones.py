from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.datos import todas_las_atenciones, total_atencion
from app.portal_web import construir_app

_CLAVE = "clave-de-prueba"
_CABECERA = {"X-Clave-Api": _CLAVE}


def _cliente() -> TestClient:
    return TestClient(construir_app(_CLAVE))


def prueba_las_rutas_de_datos_exigen_la_clave() -> None:
    cliente = _cliente()
    assert cliente.get("/atenciones").status_code == 401
    assert cliente.get("/atenciones", headers={"X-Clave-Api": "otra"}).status_code == 401
    assert cliente.get("/atenciones/AT-2026-000101").status_code == 401
    assert cliente.get("/atenciones/AT-2026-000101/exportar").status_code == 401
    assert cliente.get("/atenciones", headers=_CABECERA).status_code == 200


def prueba_sin_clave_configurada_se_rechaza_todo() -> None:
    cliente = TestClient(construir_app(""))
    assert cliente.get("/atenciones", headers={"X-Clave-Api": ""}).status_code == 401


def prueba_salud_y_portada_no_piden_clave() -> None:
    cliente = _cliente()
    assert cliente.get("/salud").json() == {"estado": "ok"}
    pagina = cliente.get("/")
    assert pagina.status_code == 200
    assert "Sistema hospitalario (simulador)" in pagina.text
    assert "AT-2026-000101" in pagina.text
    assert "J00X" not in pagina.text


def prueba_lista_resumenes_con_los_campos_del_contrato() -> None:
    lista = _cliente().get("/atenciones", headers=_CABECERA).json()
    assert len(lista) >= 12
    assert set(lista[0]) == {
        "atencion_id",
        "tipo_atencion",
        "fecha_prestacion",
        "paciente",
        "iafas_codigo",
    }
    assert set(lista[0]["paciente"]) == {
        "tipo_documento",
        "numero_documento",
        "nombres",
        "apellidos",
    }


def prueba_filtra_por_documento() -> None:
    lista = _cliente().get("/atenciones?documento=81953443", headers=_CABECERA).json()
    assert [a["atencion_id"] for a in lista] == ["AT-2026-000101"]
    assert _cliente().get("/atenciones?documento=00000000", headers=_CABECERA).json() == []


def prueba_detalle_trae_la_atencion_completa() -> None:
    respuesta = _cliente().get("/atenciones/AT-2026-000102", headers=_CABECERA)
    assert respuesta.status_code == 200
    atencion = respuesta.json()
    assert atencion["diagnostico_principal_cie10"] == "K297"
    assert atencion["procedimientos"] and atencion["farmacia"]
    assert atencion["hospitalizacion"] is None
    assert atencion["copago_cobrado"] is None


def prueba_atencion_inexistente_da_404() -> None:
    assert _cliente().get("/atenciones/AT-0", headers=_CABECERA).status_code == 404
    assert _cliente().get("/atenciones/AT-0/exportar", headers=_CABECERA).status_code == 404


def prueba_exportar_descarga_el_json() -> None:
    cliente = _cliente()
    respuesta = cliente.get("/atenciones/AT-2026-000113/exportar", headers=_CABECERA)
    assert respuesta.status_code == 200
    assert (
        respuesta.headers["content-disposition"]
        == 'attachment; filename="atencion_AT-2026-000113.json"'
    )
    assert respuesta.json() == cliente.get("/atenciones/AT-2026-000113", headers=_CABECERA).json()


def prueba_hospitalizaciones_traen_ingreso_y_alta() -> None:
    hospitalizaciones = [
        a for a in todas_las_atenciones() if a["tipo_atencion"] == "HOSPITALIZACION"
    ]
    assert len(hospitalizaciones) >= 2
    for atencion in hospitalizaciones:
        estancia = atencion["hospitalizacion"]
        assert estancia["fecha_ingreso"] == atencion["fecha_prestacion"]
        assert estancia["fecha_alta"] > estancia["fecha_ingreso"]
        for procedimiento in atencion["procedimientos"]:
            assert estancia["fecha_ingreso"] <= procedimiento["fecha"] <= estancia["fecha_alta"]
    for atencion in todas_las_atenciones():
        if atencion["tipo_atencion"] != "HOSPITALIZACION":
            assert atencion["hospitalizacion"] is None


def prueba_las_fechas_son_de_los_ultimos_siete_dias() -> None:
    hoy = date(2030, 3, 15)
    for atencion in todas_las_atenciones(hoy):
        ultima = (atencion["hospitalizacion"] or {}).get("fecha_alta", atencion["fecha_prestacion"])
        assert hoy - timedelta(days=7) <= date.fromisoformat(atencion["fecha_prestacion"]) <= hoy
        assert date.fromisoformat(ultima) <= hoy


def prueba_los_montos_son_texto_con_dos_decimales_y_coherentes() -> None:
    for atencion in todas_las_atenciones():
        for linea in atencion["procedimientos"] + atencion["farmacia"]:
            texto = linea["monto_unitario"]
            assert isinstance(texto, str) and len(texto.split(".")[1]) == 2
            assert Decimal(texto) > 0
        copago = atencion["copago_cobrado"]
        if copago is not None:
            assert len(copago["monto"].split(".")[1]) == 2
            assert 0 < Decimal(copago["monto"]) < total_atencion(atencion)
            assert copago["referencia"].startswith("B001-")


def prueba_hay_variedad_de_casos() -> None:
    atenciones = todas_las_atenciones()
    tipos = {a["tipo_atencion"] for a in atenciones}
    assert tipos == {"AMBULATORIA", "EMERGENCIA", "HOSPITALIZACION"}
    assert any(a["copago_cobrado"] for a in atenciones)
    assert any(a["copago_cobrado"] is None for a in atenciones)
    areas = {p["area"] for a in atenciones for p in a["procedimientos"]}
    assert areas == {"PROCEDIMIENTO", "LABORATORIO", "IMAGENES"}
    assert len({a["atencion_id"] for a in atenciones}) == len(atenciones)
