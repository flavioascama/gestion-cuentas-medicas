"""Prueba de ConsultorRespuestaReceptorHttp contra un servidor HTTP real y
efimero (Seccion 8.3, 9.2): igual que prueba_transmisor_ftp.py, esta habla
el protocolo HTTP de verdad, pero contra un servidor de prueba levantado en
el propio proceso -- no importa el simulador receptor_iafas (Regla 0.5: el
backend no depende de codigo de simuladores/), solo reproduce el mismo
contrato de data-testid que expone su plantilla detalle_lote.html."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.infraestructura.transmision.consultor_respuesta_receptor_http import (
    ConsultorRespuestaReceptorHttp,
    ErrorConsultaReceptor,
)

_PAGINAS: dict[str, str] = {
    "/lotes/lote_aceptado.S01": """
        <dl>
          <dt>Estado</dt><dd data-testid="detalle-estado">ACEPTADO</dd>
          <dt>Motivo</dt><dd data-testid="detalle-motivo">-</dd>
        </dl>
    """,
    "/lotes/lote_rechazado.S01": """
        <dl>
          <dt>Estado</dt><dd data-testid="detalle-estado">RECHAZADO</dd>
          <dt>Motivo</dt><dd data-testid="detalle-motivo">estructura invalida</dd>
        </dl>
    """,
    "/lotes/lote_forzado.S01": """
        <dl>
          <dt>Estado</dt>
          <dd data-testid="detalle-estado">ACEPTADO (forzado por administración)</dd>
          <dt>Motivo</dt><dd data-testid="detalle-motivo">-</dd>
        </dl>
    """,
    "/lotes/lote_sin_testid.S01": "<p>pagina sin el contrato esperado</p>",
}


class _ManejadorFalso(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 -- nombre exigido por BaseHTTPRequestHandler
        cuerpo = _PAGINAS.get(self.path)
        if cuerpo is None:
            self.send_response(404)
            self.end_headers()
            return
        datos = cuerpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, formato: str, *args: object) -> None:
        pass  # silencia el acceso log por defecto, ruidoso en pytest


@pytest.fixture
def servidor_http_local() -> Iterator[str]:
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _ManejadorFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()


async def prueba_lote_aceptado_sin_motivo(servidor_http_local: str) -> None:
    consultor = ConsultorRespuestaReceptorHttp(servidor_http_local)

    respuesta = await consultor.consultar("lote_aceptado.S01")

    assert respuesta is not None
    assert respuesta.estado == "ACEPTADO"
    assert respuesta.motivo is None


async def prueba_lote_rechazado_con_motivo(servidor_http_local: str) -> None:
    consultor = ConsultorRespuestaReceptorHttp(servidor_http_local)

    respuesta = await consultor.consultar("lote_rechazado.S01")

    assert respuesta is not None
    assert respuesta.estado == "RECHAZADO"
    assert respuesta.motivo == "estructura invalida"


async def prueba_lote_forzado_extrae_solo_el_codigo_de_estado(servidor_http_local: str) -> None:
    consultor = ConsultorRespuestaReceptorHttp(servidor_http_local)

    respuesta = await consultor.consultar("lote_forzado.S01")

    assert respuesta is not None
    assert respuesta.estado == "ACEPTADO"


async def prueba_lote_no_encontrado_devuelve_none(servidor_http_local: str) -> None:
    consultor = ConsultorRespuestaReceptorHttp(servidor_http_local)

    respuesta = await consultor.consultar("lote_inexistente.S01")

    assert respuesta is None


async def prueba_pagina_sin_contrato_esperado_lanza_error(servidor_http_local: str) -> None:
    consultor = ConsultorRespuestaReceptorHttp(servidor_http_local)

    with pytest.raises(ErrorConsultaReceptor):
        await consultor.consultar("lote_sin_testid.S01")
