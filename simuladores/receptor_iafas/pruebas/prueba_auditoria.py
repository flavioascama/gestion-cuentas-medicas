"""Pruebas de la auditoria de la IAFAS y sus comunicaciones a la IPRESS."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.auditoria import AuditoriaIafas, AuditoriaInvalidaError, Comunicacion
from app.correo import construir_correo


def _auditoria(tmp_path: Path, enviados: list[Comunicacion] | None = None) -> AuditoriaIafas:
    auditoria = AuditoriaIafas(
        tmp_path / "receptor.sqlite3", enviados.append if enviados is not None else None
    )
    auditoria.registrar_documentos(
        "lote.S01", "99553", "00001234", [("F00100000010", Decimal("118.00"))]
    )
    return auditoria


def prueba_conformidad_publica_conformidad_liquidacion_y_pago(tmp_path: Path) -> None:
    auditoria = _auditoria(tmp_path)
    emitidas = auditoria.auditar("F00100000010", "CONFORME")

    assert [c.tipo for c in emitidas] == ["AUDITORIA_CONFORME", "LIQUIDACION", "PAGO"]
    assert emitidas[1].datos == {"monto_liquidado": "118.00", "es_parcial": False}
    assert [c.codigo for c in auditoria.comunicaciones("00001234")] == [c.codigo for c in emitidas]
    with pytest.raises(AuditoriaInvalidaError):
        auditoria.auditar("F00100000010", "CONFORME")


def prueba_glosa_total_aceptada_liquida_el_total(tmp_path: Path) -> None:
    auditoria = _auditoria(tmp_path)
    (observacion,) = auditoria.auditar("F00100000010", "GLOSA", motivo_codigo="OBS-04")
    assert observacion.datos["es_parcial"] is False

    siguientes = auditoria.responder(observacion.codigo, "00001234", "Se adjunta sustento", None)
    assert [c.tipo for c in siguientes] == ["LIQUIDACION", "PAGO"]
    assert siguientes[0].datos["monto_liquidado"] == "118.00"
    with pytest.raises(AuditoriaInvalidaError):
        auditoria.responder(observacion.codigo, "00001234", "otra vez", None)


def prueba_glosa_mantenida_una_vez_genera_otra_observacion(tmp_path: Path) -> None:
    auditoria = _auditoria(tmp_path)
    (primera,) = auditoria.auditar(
        "F00100000010", "GLOSA", motivo_codigo="OBS-04", decision_respuesta="MANTENER"
    )
    (segunda,) = auditoria.responder(primera.codigo, "00001234", "respuesta", None)
    assert segunda.tipo == "OBSERVACION"
    finales = auditoria.responder(segunda.codigo, "00001234", "respuesta", None)
    assert [c.tipo for c in finales] == ["LIQUIDACION", "PAGO"]


def prueba_glosa_parcial_liquida_lo_no_objetado(tmp_path: Path) -> None:
    auditoria = _auditoria(tmp_path)
    (observacion,) = auditoria.auditar(
        "F00100000010", "GLOSA_PARCIAL", motivo_codigo="OBS-07", monto_glosado=Decimal("18.00")
    )
    liquidacion, pago = auditoria.responder(observacion.codigo, "00001234", "aceptamos", None)
    assert liquidacion.datos == {"monto_liquidado": "100.00", "es_parcial": True}
    assert pago.datos == {"monto_pagado": "100.00"}


def prueba_el_canal_correo_envia_cada_comunicacion(tmp_path: Path) -> None:
    enviados: list[Comunicacion] = []
    auditoria = _auditoria(tmp_path, enviados)
    auditoria.auditar("F00100000010", "GLOSA", canal="CORREO", motivo_codigo="OBS-01")

    (correo,) = enviados
    mensaje = construir_correo(correo, "auditoria@iafas.test", "cuentasmedicas@clinica.test")
    assert mensaje["X-Comunicacion-Iafas"] == correo.codigo
    adjuntos = list(mensaje.iter_attachments())
    assert adjuntos[0].get_filename() == "comunicacion.json"


def prueba_solo_responde_la_ipress_de_la_comunicacion(tmp_path: Path) -> None:
    auditoria = _auditoria(tmp_path)
    (observacion,) = auditoria.auditar("F00100000010", "GLOSA", motivo_codigo="OBS-04")
    with pytest.raises(AuditoriaInvalidaError):
        auditoria.responder(observacion.codigo, "99999999", "respuesta", None)
