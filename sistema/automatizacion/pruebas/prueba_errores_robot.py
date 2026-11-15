"""Mensaje y clase del asegurado no encontrado en ACREDITA SALUD
(2026-11-12): es una respuesta definitiva (SIN_RESULTADO, sin reintentos)
y su mensaje es para el analista, sin nombrar al simulador."""

from __future__ import annotations

from trabajador.robots.robot_acreditacion import ErrorAseguradoNoEncontrado
from trabajador.soporte.errores import ErrorSinResultado


def prueba_asegurado_no_encontrado_es_un_resultado_sin_reintento() -> None:
    error = ErrorAseguradoNoEncontrado("1", "73457855")
    assert isinstance(error, ErrorSinResultado)
    assert str(error) == "ACREDITA SALUD no encontró al asegurado con DNI 73457855."
    assert "simulador" not in str(error).lower()


def prueba_tipo_de_documento_desconocido_se_nombra_generico() -> None:
    assert str(ErrorAseguradoNoEncontrado("9", "X1")).endswith("con documento X1.")
