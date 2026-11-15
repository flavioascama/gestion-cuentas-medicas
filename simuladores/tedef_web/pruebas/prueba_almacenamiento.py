from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.almacenamiento import AlmacenamientoTedefWeb
from app.revision_forma import IdentidadLote, ObservacionForma

_IDENTIDAD = IdentidadLote(
    ruc="20690951848",
    codigo_ipress="15995250",
    codigo_iafas="99553",
    numero_lote="1234567",
    periodo="201606",
    fecha="20130605",
)


def _almacenamiento(tmp_path: Path) -> AlmacenamientoTedefWeb:
    return AlmacenamientoTedefWeb(tmp_path / "tedef_web.sqlite3")


def prueba_registrar_y_listar_por_validar(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    lote_id = almacenamiento.registrar_intento(
        _IDENTIDAD, "REGISTRADO", {"T1": ("dfac_x.txt", b"0" * 10)}, "usuario_demo"
    )
    lotes = almacenamiento.listar_por_validar()
    assert [lote.id for lote in lotes] == [lote_id]
    assert lotes[0].estado == "REGISTRADO"


def prueba_existe_lote_activo_ignora_eliminados(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    lote_id = almacenamiento.registrar_intento(_IDENTIDAD, "REGISTRADO", {}, "usuario_demo")
    assert almacenamiento.existe_lote_activo(_IDENTIDAD)
    almacenamiento.eliminar(lote_id, "usuario_demo")
    assert not almacenamiento.existe_lote_activo(_IDENTIDAD)


def prueba_marcar_validando_y_luego_validado(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    lote_id = almacenamiento.registrar_intento(_IDENTIDAD, "REGISTRADO", {}, "usuario_demo")
    almacenamiento.marcar_validando(lote_id, datetime.now() + timedelta(seconds=5))
    assert almacenamiento.obtener(lote_id).estado == "VALIDANDO"  # type: ignore[union-attr]

    almacenamiento.marcar_validado(lote_id, "937_x.S01", b"contenido-cifrado")
    lote = almacenamiento.obtener(lote_id)
    assert lote is not None
    assert lote.estado == "VALIDADO"
    assert lote.nombre_s01 == "937_x.S01"
    assert almacenamiento.contenido_s01(lote_id) == b"contenido-cifrado"


def prueba_listar_por_enviar_solo_incluye_validados(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    lote_id = almacenamiento.registrar_intento(_IDENTIDAD, "REGISTRADO", {}, "usuario_demo")
    assert almacenamiento.listar_por_enviar() == []
    almacenamiento.marcar_validado(lote_id, "937_x.S01", b"x")
    assert [lote.id for lote in almacenamiento.listar_por_enviar()] == [lote_id]

    almacenamiento.marcar_enviado(lote_id)
    assert almacenamiento.listar_por_enviar() == []
    assert [lote.id for lote in almacenamiento.listar_enviados()] == [lote_id]


def prueba_observaciones_se_asocian_a_la_etapa_correcta(tmp_path: Path) -> None:
    almacenamiento = _almacenamiento(tmp_path)
    lote_id = almacenamiento.registrar_intento(_IDENTIDAD, "RECHAZADO_FORMA", {}, "usuario_demo")
    almacenamiento.registrar_observaciones_forma(
        lote_id, (ObservacionForma("T1", "SIM-FALT", "Faltan tablas obligatorias."),)
    )
    observaciones = almacenamiento.observaciones_de(lote_id, "FORMA")
    assert len(observaciones) == 1
    assert observaciones[0]["codigo_error"] == "SIM-FALT"
    assert almacenamiento.observaciones_de(lote_id, "DETALLADA") == []
