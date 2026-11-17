"""Cada aseguradora tiene su propio portal: la entrada las lista y cada
portal muestra solo lo suyo. Las rutas que consulta el sistema por programa
siguen respondiendo igual, sin aseguradora en la direccion."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.almacenamiento import AlmacenamientoReceptor
from app.auditoria import AuditoriaIafas
from app.portal_web import _volver, cargar_aseguradoras, construir_app

_ASEGURADORAS = {"05292": "Barrios IAFAS", "99553": "Simo IAFAS"}
_LOTE_BARRIOS = "937_20690951848_15995250_05292_0000001_202607_20261115.S01"
_LOTE_SIMO = "937_20690951848_15995250_99553_0000016_202609_20261115.S01"


async def _pedir(app: Any, ruta: str) -> tuple[int, str]:
    """GET directo a la aplicacion ASGI: el simulador no depende de httpx."""
    mensajes: list[dict[str, Any]] = []

    async def recibir() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def enviar(mensaje: dict[str, Any]) -> None:
        mensajes.append(mensaje)

    alcance = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": ruta,
        "raw_path": ruta.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("prueba", 80),
        "client": ("prueba", 1),
    }
    await app(alcance, recibir, enviar)
    estado = next(m["status"] for m in mensajes if m["type"] == "http.response.start")
    cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
    return estado, cuerpo.decode("utf-8")


def _obtener(app: Any, ruta: str) -> tuple[int, str]:
    return asyncio.run(_pedir(app, ruta))


def _app_con_dos_lotes(tmp_path: Path) -> Any:
    base = tmp_path / "receptor.sqlite3"
    almacenamiento = AlmacenamientoReceptor(base)
    for archivo, numero, iafas in (
        (_LOTE_BARRIOS, "0000001", "05292"),
        (_LOTE_SIMO, "0000016", "99553"),
    ):
        almacenamiento.registrar(
            nombre_archivo=archivo,
            numero_lote=numero,
            codigo_iafas=iafas,
            codigo_ipress="15995250",
            estado="ACEPTADO",
            motivo=None,
        )
    return construir_app(almacenamiento, AuditoriaIafas(base), None, _ASEGURADORAS)


def prueba_la_entrada_lista_las_aseguradoras_con_sus_lotes(tmp_path: Path) -> None:
    estado, html = _obtener(_app_con_dos_lotes(tmp_path), "/")
    assert estado == 200
    assert 'href="/aseguradora/05292"' in html and 'href="/aseguradora/99553"' in html
    assert "Barrios IAFAS" in html and "Simo IAFAS" in html


def prueba_cada_portal_muestra_su_nombre_y_solo_sus_lotes(tmp_path: Path) -> None:
    estado, html = _obtener(_app_con_dos_lotes(tmp_path), "/aseguradora/05292")
    assert estado == 200
    assert "Barrios IAFAS" in html
    assert _LOTE_BARRIOS in html and _LOTE_SIMO not in html
    # Los enlaces del portal se quedan dentro de el.
    assert f'href="/aseguradora/05292/lotes/{_LOTE_BARRIOS}"' in html
    assert 'href="/aseguradora/05292/auditoria"' in html


def prueba_un_portal_no_abre_el_lote_de_otra_aseguradora(tmp_path: Path) -> None:
    app = _app_con_dos_lotes(tmp_path)
    assert _obtener(app, f"/aseguradora/05292/lotes/{_LOTE_BARRIOS}")[0] == 200
    assert _obtener(app, f"/aseguradora/05292/lotes/{_LOTE_SIMO}")[0] == 404


def prueba_una_aseguradora_desconocida_responde_404(tmp_path: Path) -> None:
    assert _obtener(_app_con_dos_lotes(tmp_path), "/aseguradora/00000")[0] == 404


def prueba_las_rutas_que_consulta_el_sistema_no_cambian(tmp_path: Path) -> None:
    app = _app_con_dos_lotes(tmp_path)
    estado, html = _obtener(app, f"/lotes/{_LOTE_SIMO}")
    assert estado == 200
    assert 'data-testid="detalle-estado"' in html
    assert _obtener(app, "/comunicaciones")[0] == 200
    assert _obtener(app, "/auditoria")[0] == 200


def prueba_volver_solo_acepta_un_portal_de_este_sitio() -> None:
    assert _volver("/aseguradora/05292/auditoria", "/auditoria") == "/aseguradora/05292/auditoria"
    assert _volver("https://otro.sitio/", "/auditoria") == "/auditoria"
    assert _volver("", "/auditoria") == "/auditoria"


def prueba_cargar_aseguradoras_lee_la_semilla_y_tolera_que_falte(tmp_path: Path) -> None:
    ruta = tmp_path / "iafas.json"
    assert cargar_aseguradoras(ruta) == {}
    ruta.write_text(
        '{"iafas": [{"codigo": "05292", "razon_social": "Barrios IAFAS"}]}', encoding="utf-8"
    )
    assert cargar_aseguradoras(ruta) == {"05292": "Barrios IAFAS"}
