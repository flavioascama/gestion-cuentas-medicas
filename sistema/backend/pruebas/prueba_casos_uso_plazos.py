"""Pruebas de RevisarVencimientos (CU-11, Seccion 5.2.4.3, Tabla 61) con
un doble de RepositorioPlazos -- sin Postgres real: las consultas SQL en
si se verifican aparte (pruebas/prueba_repositorio_plazos.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.dominio.plazos.casos_uso import RevisarVencimientos
from app.dominio.plazos.valores import (
    CuentaConPlazo,
    CuentaConVigenciaCartaGarantia,
    ObservacionConPlazo,
)
from app.dominio.puertos_comunes import Evento, Observabilidad

_AHORA = datetime(2026, 11, 8, 10, 0, 0)
_DIAS_AVISO = 2
_DIAS_AVISO_CARTA_GARANTIA = 5


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _MedicionesFalso:
    async def registrar(self, medicion: object) -> None:
        pass


@dataclass
class _RepositorioPlazosFalso:
    observaciones: list[ObservacionConPlazo] = field(default_factory=list)
    rechazadas: list[CuentaConPlazo] = field(default_factory=list)
    en_auditoria: list[CuentaConPlazo] = field(default_factory=list)
    liquidadas: list[CuentaConPlazo] = field(default_factory=list)
    cartas_garantia: list[CuentaConVigenciaCartaGarantia] = field(default_factory=list)

    async def observaciones_abiertas(self) -> list[ObservacionConPlazo]:
        return self.observaciones

    async def cuentas_rechazadas(self) -> list[CuentaConPlazo]:
        return self.rechazadas

    async def cuentas_en_auditoria(self) -> list[CuentaConPlazo]:
        return self.en_auditoria

    async def cuentas_liquidadas(self) -> list[CuentaConPlazo]:
        return self.liquidadas

    async def cuentas_con_carta_garantia_por_vencer(
        self,
    ) -> list[CuentaConVigenciaCartaGarantia]:
        return self.cartas_garantia


def _caso_uso(
    repositorio: _RepositorioPlazosFalso, registro_eventos: _RegistroEventosFalso
) -> RevisarVencimientos:
    return RevisarVencimientos(
        repositorio=repositorio,
        observabilidad=Observabilidad(eventos=registro_eventos, mediciones=_MedicionesFalso()),
        reloj=_RelojFijo(),
        dias_aviso_previo_vencimiento=_DIAS_AVISO,
        dias_aviso_vigencia_carta_garantia=_DIAS_AVISO_CARTA_GARANTIA,
    )


# --- Hito 1: respuesta a una observacion ---------------------------------


async def prueba_observacion_vigente_no_genera_evento() -> None:
    repositorio = _RepositorioPlazosFalso(
        observaciones=[
            ObservacionConPlazo(
                observacion_id=1,
                cuenta_medica_id=10,
                plazo_dias=7,
                abierta_desde=_AHORA,
                ya_avisada=False,
                ya_escalada=False,
            )
        ]
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(repositorio, registro_eventos).ejecutar()

    assert resumen.observaciones.revisados == 1
    assert resumen.observaciones.avisados == 0
    assert resumen.observaciones.escalados == 0
    assert registro_eventos.eventos == []


async def prueba_observacion_proxima_a_vencer_avisa_una_sola_vez() -> None:
    hito = ObservacionConPlazo(
        observacion_id=1,
        cuenta_medica_id=10,
        plazo_dias=7,
        abierta_desde=_AHORA - timedelta(days=6),  # vence en 1 dia, dentro de la ventana de 2.
        ya_avisada=False,
        ya_escalada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(observaciones=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.observaciones.avisados == 1
    assert registro_eventos.eventos[0].tipo_evento == "OBSERVACION_PLAZO_PROXIMO_A_VENCER"
    assert registro_eventos.eventos[0].actor == "temporizador_sistema"
    assert registro_eventos.eventos[0].estado_previo is None
    assert registro_eventos.eventos[0].estado_nuevo is None
    assert registro_eventos.eventos[0].cuenta_medica_id == 10
    assert registro_eventos.eventos[0].datos["observacion_id"] == 1

    # Ya avisada: una segunda corrida no vuelve a avisar.
    hito_ya_avisado = ObservacionConPlazo(
        observacion_id=1,
        cuenta_medica_id=10,
        plazo_dias=7,
        abierta_desde=hito.abierta_desde,
        ya_avisada=True,
        ya_escalada=False,
    )
    registro_eventos_2 = _RegistroEventosFalso()
    resumen_2 = await _caso_uso(
        _RepositorioPlazosFalso(observaciones=[hito_ya_avisado]), registro_eventos_2
    ).ejecutar()
    assert resumen_2.observaciones.avisados == 0
    assert registro_eventos_2.eventos == []


async def prueba_observacion_vencida_escala_y_no_avisa() -> None:
    hito = ObservacionConPlazo(
        observacion_id=2,
        cuenta_medica_id=11,
        plazo_dias=7,
        abierta_desde=_AHORA - timedelta(days=8),
        ya_avisada=True,
        ya_escalada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(observaciones=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.observaciones.avisados == 0
    assert resumen.observaciones.escalados == 1
    assert registro_eventos.eventos[0].tipo_evento == "OBSERVACION_PLAZO_VENCIDO_ESCALADO"


# --- Hito 2: reenvio de un lote rechazado --------------------------------


async def prueba_lote_rechazado_vencido_escala() -> None:
    hito = CuentaConPlazo(
        cuenta_medica_id=20,
        plazo_dias=5,
        hito_desde=_AHORA - timedelta(days=6),
        ya_avisada=True,
        ya_escalada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(rechazadas=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.lotes_rechazados.escalados == 1
    assert registro_eventos.eventos[0].tipo_evento == "LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO"


# --- Hito 3: comunicacion del resultado de la auditoria ------------------


async def prueba_auditoria_vencida_se_marca_excedida() -> None:
    hito = CuentaConPlazo(
        cuenta_medica_id=30,
        plazo_dias=30,
        hito_desde=_AHORA - timedelta(days=31),
        ya_avisada=True,
        ya_escalada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(en_auditoria=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.auditorias.escalados == 1
    assert registro_eventos.eventos[0].tipo_evento == "AUDITORIA_EXCEDIDA"
    # Senal informativa (Tabla 61): no es un estado de la Tabla 58.
    assert registro_eventos.eventos[0].estado_nuevo is None


# --- Hito 4: pago de una liquidacion comunicada --------------------------


async def prueba_liquidacion_proxima_a_vencer_avisa() -> None:
    hito = CuentaConPlazo(
        cuenta_medica_id=40,
        plazo_dias=30,
        hito_desde=_AHORA - timedelta(days=29),
        ya_avisada=False,
        ya_escalada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(liquidadas=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.liquidaciones.avisados == 1
    assert registro_eventos.eventos[0].tipo_evento == "LIQUIDACION_PAGO_PROXIMO_A_VENCER"


# --- Hito 5: vigencia de la carta de garantia ----------------------------


async def prueba_carta_garantia_proxima_a_vencer_avisa() -> None:
    hito = CuentaConVigenciaCartaGarantia(
        cuenta_medica_id=50,
        vigente_hasta=_AHORA.date() + timedelta(days=3),
        ya_avisada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(cartas_garantia=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.cartas_garantia.avisados == 1
    assert resumen.cartas_garantia.escalados == 0
    assert registro_eventos.eventos[0].tipo_evento == "CARTA_GARANTIA_PROXIMA_A_VENCER"


async def prueba_carta_garantia_lejos_de_vencer_no_avisa() -> None:
    hito = CuentaConVigenciaCartaGarantia(
        cuenta_medica_id=51,
        vigente_hasta=_AHORA.date() + timedelta(days=60),
        ya_avisada=False,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(cartas_garantia=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.cartas_garantia.avisados == 0
    assert registro_eventos.eventos == []


async def prueba_carta_garantia_ya_avisada_no_vuelve_a_avisar() -> None:
    hito = CuentaConVigenciaCartaGarantia(
        cuenta_medica_id=52,
        vigente_hasta=_AHORA.date() + timedelta(days=1),
        ya_avisada=True,
    )
    registro_eventos = _RegistroEventosFalso()
    resumen = await _caso_uso(
        _RepositorioPlazosFalso(cartas_garantia=[hito]), registro_eventos
    ).ejecutar()

    assert resumen.cartas_garantia.avisados == 0
    assert registro_eventos.eventos == []
