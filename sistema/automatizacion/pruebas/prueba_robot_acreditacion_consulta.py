"""El robot de acreditacion lee del resultado de la consulta el codigo de
asegurado, el tipo de afiliacion y la IAFAS, y marca NO ACREDITABLE al
asegurado que figura en otra aseguradora. Con una pagina falsa que
responde por selector, sin navegador."""

from __future__ import annotations

from typing import Any

import pytest
from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion, es_acreditable

from trabajador.robots.robot_acreditacion import (
    AdaptadorAcreditacionWeb,
    ErrorRobotAcreditacion,
)
from trabajador.soporte.selectores import obtener_selector

_TEXTOS = {
    ("consulta_iafas", "codigo_asegurado"): "99553-81953443",
    ("consulta_iafas", "tipo_afiliacion"): "1",
    ("consulta_iafas", "codigo_iafas"): "99553",
    ("consulta_iafas", "nombre_iafas"): "IAFAS Salud Total (ficticia)",
    ("consulta_iafas", "plan"): "PLAN SALUD PREFERENTE",
    ("consulta_iafas", "vigente_desde"): "2025-09-15",
    ("consulta_iafas", "vigente_hasta"): "2027-09-15",
    ("evaluacion", "condicion_cobertura"): "ACREDITABLE",
    ("evaluacion", "tipo_copago"): "fijo",
    ("evaluacion", "monto_copago_fijo"): "S/ 25.50",
    ("documento", "codigo_autorizacion"): "AUT0000099",
}


class _Localizador:
    def __init__(self, texto: str | None) -> None:
        self._texto = texto

    async def count(self) -> int:
        return 0 if self._texto is None else 1

    async def text_content(self) -> str | None:
        return self._texto


class _PaginaFalsa:
    url = "http://simulador/documento"

    def __init__(self, textos: dict[tuple[str, str], str]) -> None:
        self._por_selector = {obtener_selector(s, c): t for (s, c), t in textos.items()}

    def locator(self, selector: str) -> _Localizador:
        return _Localizador(self._por_selector.get(selector))

    async def _nada(self, *_: Any, **__: Any) -> None:
        return None

    goto = select_option = fill = click = wait_for_selector = _nada


def _robot() -> AdaptadorAcreditacionWeb:
    robot = AdaptadorAcreditacionWeb(None, None, None)  # type: ignore[arg-type]

    async def _sin_evidencia(*_: Any) -> str:
        return "evidencia_acreditacion/1/documento.png.cifrado"

    robot._guardar_evidencia = _sin_evidencia  # type: ignore[method-assign]
    return robot


def _contexto(codigo_iafas: str) -> ContextoCuentaAcreditacion:
    return ContextoCuentaAcreditacion(
        cuenta_medica_id=1,
        tipo_documento_paciente="1",
        numero_documento_paciente="81953443",
        codigo_iafas=codigo_iafas,
    )


async def prueba_lee_codigo_de_asegurado_y_afiliacion_de_la_plataforma() -> None:
    resultado = await _robot()._consultar_y_acreditar(  # noqa: SLF001
        _PaginaFalsa(_TEXTOS),  # type: ignore[arg-type]
        _contexto("99553"),
        1,
    )
    assert resultado.codigo_asegurado == "99553-81953443"
    assert resultado.tipo_afiliacion == "1"
    assert resultado.condicion_cobertura == "ACREDITABLE"
    assert resultado.tipo_copago == "fijo"
    assert str(resultado.monto_copago_fijo) == "25.50"


async def prueba_aseguradora_distinta_deja_no_acreditable() -> None:
    resultado = await _robot()._consultar_y_acreditar(  # noqa: SLF001
        _PaginaFalsa(_TEXTOS),  # type: ignore[arg-type]
        _contexto("05292"),
        1,
    )
    assert resultado.condicion_cobertura == (
        "NO ACREDITABLE: el asegurado figura en otra aseguradora (IAFAS Salud Total (ficticia))"
    )
    assert not es_acreditable(resultado.condicion_cobertura)


async def prueba_sin_codigo_de_asegurado_en_pantalla_falla_con_mensaje() -> None:
    textos = {k: v for k, v in _TEXTOS.items() if k[1] != "codigo_asegurado"}
    with pytest.raises(ErrorRobotAcreditacion, match="codigo_asegurado"):
        await _robot().leer_consulta(_PaginaFalsa(textos))  # type: ignore[arg-type]
