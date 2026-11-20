"""Pruebas del plazo del reporte mensual a SUSALUD (Resolucion
043-2025-SUSALUD/S): la excepcion de diciembre y la declaracion jurada de
los meses sin facturacion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from app.dominio.plazos.declaracion_susalud import (
    TIPO_EVENTO_DECLARACION,
    ErrorPeriodoConLotes,
    ErrorPeriodoInvalido,
    ErrorPeriodoNoCerrado,
    ErrorPeriodoYaDeclarado,
    RegistrarDeclaracionSinFacturacion,
)
from app.dominio.plazos.susalud import (
    TIPO_AVISO_SUSALUD,
    TIPO_ESCALADO_SUSALUD,
    ConsultarControlSusalud,
    EstadoEnvioSusalud,
    LotePendienteSusalud,
    LotesPeriodo,
    RevisarPlazoSusalud,
    fecha_limite_declaracion_susalud,
    fecha_limite_envio_susalud,
)
from app.dominio.puertos_comunes import Evento, Observabilidad

# 13/11/2026 10:00 en Lima.
_AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
_ENVIO = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _Eventos:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _Mediciones:
    async def registrar(self, medicion: object) -> None:
        pass


@dataclass
class _Repositorio:
    periodos: list[LotesPeriodo] = field(default_factory=list)
    declaradas: dict[str, datetime] = field(default_factory=dict)
    avisados: dict[str, frozenset[str]] = field(default_factory=dict)

    async def lotes_por_periodo(self) -> list[LotesPeriodo]:
        return self.periodos

    async def lotes_pendientes_envio(self) -> list[LotePendienteSusalud]:
        return []

    async def declaraciones(self) -> dict[str, datetime]:
        return self.declaradas

    async def avisos_sin_lotes(self) -> dict[str, frozenset[str]]:
        return self.avisados

    async def registrar_declaracion(self, periodo: str, registrada_por: str) -> datetime:
        self.declaradas[periodo] = _AHORA
        return _AHORA


def _repositorio() -> _Repositorio:
    # 202608 con lotes enviados; 202609 y 202610 sin lotes.
    return _Repositorio(periodos=[LotesPeriodo("202608", 1, 0, _ENVIO)])


# --- fecha limite ---------------------------------------------------------


def prueba_diciembre_vence_el_ultimo_dia_habil_de_enero() -> None:
    # El 31/01/2027 es domingo: el ultimo dia habil es el viernes 29.
    assert fecha_limite_envio_susalud("202612", frozenset()) == date(2027, 1, 29)


def prueba_diciembre_descuenta_los_feriados_de_enero() -> None:
    feriados = frozenset({date(2027, 1, 29), date(2027, 1, 28)})
    assert fecha_limite_envio_susalud("202612", feriados) == date(2027, 1, 27)
    # Un feriado de inicio de enero no mueve el ultimo dia habil.
    assert fecha_limite_envio_susalud("202612", frozenset({date(2027, 1, 1)})) == date(2027, 1, 29)


def prueba_los_meses_normales_siguen_en_el_decimo_dia_habil() -> None:
    assert fecha_limite_envio_susalud("202610", frozenset()) == date(2026, 11, 13)
    assert fecha_limite_envio_susalud("202611", frozenset()) == date(2026, 12, 14)
    assert fecha_limite_envio_susalud("202611", frozenset({date(2026, 12, 8)})) == date(
        2026, 12, 15
    )
    assert fecha_limite_envio_susalud("202601", frozenset()) == date(2026, 2, 13)


# --- control de plazos ----------------------------------------------------


async def prueba_mes_sin_lotes_sin_declarar_corre_como_reporte_pendiente() -> None:
    controles = await ConsultarControlSusalud(
        _repositorio(), _RelojFijo(), frozenset(), dias_aviso_previo=2
    ).ejecutar()
    por_periodo = {c.periodo: c for c in controles}

    assert por_periodo["202609"].estado == EstadoEnvioSusalud.VENCIDO
    assert por_periodo["202609"].fecha_limite == date(2026, 10, 14)
    assert por_periodo["202609"].declarada_en is None
    assert por_periodo["202610"].estado == EstadoEnvioSusalud.POR_VENCER


async def prueba_mes_sin_lotes_declarado_queda_sin_lotes_con_su_fecha() -> None:
    repositorio = _repositorio()
    repositorio.declaradas["202609"] = _AHORA
    controles = await ConsultarControlSusalud(
        repositorio, _RelojFijo(), frozenset(), dias_aviso_previo=2
    ).ejecutar()
    control = next(c for c in controles if c.periodo == "202609")

    assert control.estado == EstadoEnvioSusalud.SIN_LOTES
    assert control.declarada_en == _AHORA


# --- avisos del temporizador ---------------------------------------------


async def prueba_el_temporizador_avisa_y_escala_los_meses_sin_declarar_una_vez() -> None:
    repositorio = _repositorio()
    eventos = _Eventos()
    revisar = RevisarPlazoSusalud(
        repositorio,
        Observabilidad(eventos=eventos, mediciones=_Mediciones()),
        _RelojFijo(),
        frozenset(),
        dias_aviso_previo=2,
    )
    resumen = await revisar.ejecutar()

    assert (resumen.avisados, resumen.escalados) == (1, 1)
    assert sorted((e.tipo_evento, e.datos["periodo"]) for e in eventos.eventos) == [
        (TIPO_AVISO_SUSALUD, "202610"),
        (TIPO_ESCALADO_SUSALUD, "202609"),
    ]
    assert all(e.cuenta_medica_id is None and e.lote_id is None for e in eventos.eventos)

    # Con los avisos ya registrados no se repite ninguno.
    repositorio.avisados = {
        "202609": frozenset({TIPO_ESCALADO_SUSALUD}),
        "202610": frozenset({TIPO_AVISO_SUSALUD}),
    }
    eventos.eventos.clear()
    assert (await revisar.ejecutar()).avisados == 0
    assert eventos.eventos == []


async def prueba_el_temporizador_no_avisa_un_mes_ya_declarado() -> None:
    repositorio = _repositorio()
    repositorio.declaradas = {"202609": _AHORA, "202610": _AHORA}
    eventos = _Eventos()
    resumen = await RevisarPlazoSusalud(
        repositorio,
        Observabilidad(eventos=eventos, mediciones=_Mediciones()),
        _RelojFijo(),
        frozenset(),
        dias_aviso_previo=2,
    ).ejecutar()

    assert (resumen.revisados, resumen.avisados, resumen.escalados) == (0, 0, 0)
    assert eventos.eventos == []


# --- registrar la declaracion --------------------------------------------


def _caso(repositorio: _Repositorio, eventos: _Eventos) -> RegistrarDeclaracionSinFacturacion:
    return RegistrarDeclaracionSinFacturacion(repositorio, eventos, _RelojFijo())


async def prueba_registrar_la_declaracion_guarda_y_deja_el_evento() -> None:
    repositorio, eventos = _repositorio(), _Eventos()
    registrada = await _caso(repositorio, eventos).ejecutar("202609", "analista1", 7)

    assert registrada == _AHORA
    assert "202609" in repositorio.declaradas
    (evento,) = eventos.eventos
    assert evento.tipo_evento == TIPO_EVENTO_DECLARACION
    assert evento.datos == {"periodo": "202609"}
    assert evento.sesion_usuario_id == 7
    assert evento.cuenta_medica_id is None


async def prueba_rechaza_un_periodo_que_aun_no_cerro() -> None:
    eventos = _Eventos()
    for periodo in ("202611", "202701"):
        with pytest.raises(ErrorPeriodoNoCerrado):
            await _caso(_repositorio(), eventos).ejecutar(periodo, "analista1", 7)
    assert eventos.eventos == []


async def prueba_rechaza_un_periodo_con_lotes_que_reportar() -> None:
    repositorio, eventos = _repositorio(), _Eventos()
    with pytest.raises(ErrorPeriodoConLotes):
        await _caso(repositorio, eventos).ejecutar("202608", "analista1", 7)
    assert repositorio.declaradas == {} and eventos.eventos == []


async def prueba_rechaza_un_periodo_ya_declarado() -> None:
    repositorio, eventos = _repositorio(), _Eventos()
    await _caso(repositorio, eventos).ejecutar("202609", "analista1", 7)
    with pytest.raises(ErrorPeriodoYaDeclarado):
        await _caso(repositorio, eventos).ejecutar("202609", "analista1", 7)
    assert len(eventos.eventos) == 1


async def prueba_rechaza_un_periodo_mal_formado() -> None:
    for periodo in ("2026", "202613", "abcdef"):
        with pytest.raises(ErrorPeriodoInvalido):
            await _caso(_repositorio(), _Eventos()).ejecutar(periodo, "analista1", 7)


def prueba_la_declaracion_de_diciembre_vence_a_los_diez_dias_habiles() -> None:
    """Articulo 9: la excepcion de diciembre es del envio, no de la
    declaracion del mes sin facturacion."""
    assert fecha_limite_declaracion_susalud("202612", frozenset()) == date(2027, 1, 14)
    assert fecha_limite_declaracion_susalud("202610", frozenset()) == date(2026, 11, 13)
