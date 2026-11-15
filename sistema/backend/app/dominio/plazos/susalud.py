"""Control del envio a SUSALUD (RT-05, RI-16): "remitir a SUSALUD dentro
de los diez dias habiles del mes siguiente", con la fecha de envio, el
control de ese plazo y la identificacion de los meses sin lotes.

Hasta la verificacion de cumplimiento del 2026-11-12 solo se registraba la
fecha de envio (`lote_facturacion.enviado_susalud_en`). Aqui se calcula,
por periodo de facturacion, la fecha limite y el estado del envio, y el
temporizador avisa por cada lote que sigue sin enviarse cerca o despues de
esa fecha.

Dias habiles: lunes a viernes, menos los feriados configurados (FERIADOS).
Sin feriados configurados la fecha limite calculada nunca es posterior a
la real (a lo sumo es anterior): el control avisa antes, nunca despues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol

from app.dominio.plazos.valores import ResumenHito
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

DIAS_HABILES_ENVIO_SUSALUD = 10
# El Peru no aplica horario de verano: UTC-5 todo el anio.
ZONA_PERU = timezone(timedelta(hours=-5))
_ACTOR_TEMPORIZADOR = "temporizador_sistema"
TIPO_AVISO_SUSALUD = "SUSALUD_ENVIO_PROXIMO_A_VENCER"
TIPO_ESCALADO_SUSALUD = "SUSALUD_ENVIO_VENCIDO_ESCALADO"


def periodo_siguiente(periodo: str) -> str:
    anio, mes = int(periodo[:4]), int(periodo[4:6])
    return f"{anio + mes // 12:04d}{mes % 12 + 1:02d}"


def periodo_de(fecha: date) -> str:
    return f"{fecha.year:04d}{fecha.month:02d}"


def fecha_limite_envio_susalud(periodo: str, feriados: frozenset[date]) -> date:
    """Decimo dia habil del mes siguiente al periodo facturado."""
    siguiente = periodo_siguiente(periodo)
    dia = date(int(siguiente[:4]), int(siguiente[4:6]), 1)
    contados = 0
    while True:
        if dia.weekday() < 5 and dia not in feriados:
            contados += 1
            if contados == DIAS_HABILES_ENVIO_SUSALUD:
                return dia
        dia += timedelta(days=1)


class EstadoEnvioSusalud(StrEnum):
    ENVIADO = "ENVIADO"
    ENVIADO_FUERA_DE_PLAZO = "ENVIADO_FUERA_DE_PLAZO"
    PENDIENTE = "PENDIENTE"
    POR_VENCER = "POR_VENCER"
    VENCIDO = "VENCIDO"
    SIN_LOTES = "SIN_LOTES"


@dataclass(frozen=True, slots=True)
class LotesPeriodo:
    """Lo que el repositorio resume de los lotes de un periodo."""

    periodo: str
    lotes: int
    pendientes_envio: int
    ultimo_envio: datetime | None


@dataclass(frozen=True, slots=True)
class LotePendienteSusalud:
    lote_id: int
    periodo: str
    ya_avisado: bool
    ya_escalado: bool


@dataclass(frozen=True, slots=True)
class ControlPeriodoSusalud:
    periodo: str
    lotes: int
    pendientes_envio: int
    fecha_limite: date
    ultimo_envio: datetime | None
    estado: EstadoEnvioSusalud


class RepositorioControlSusalud(Protocol):
    async def lotes_por_periodo(self) -> list[LotesPeriodo]:
        """Un resumen por cada periodo que tiene al menos un lote."""
        ...

    async def lotes_pendientes_envio(self) -> list[LotePendienteSusalud]:
        """Lotes sujetos a envio que aun no se enviaron a SUSALUD."""
        ...


def _hoy(reloj: Reloj) -> date:
    ahora = reloj.ahora()
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=UTC)
    return ahora.astimezone(ZONA_PERU).date()


class ConsultarControlSusalud:
    """Un renglon por periodo, desde el primero con lotes hasta el ultimo
    mes cerrado: los meses intermedios sin ningun lote quedan SIN_LOTES."""

    def __init__(
        self,
        repositorio: RepositorioControlSusalud,
        reloj: Reloj,
        feriados: frozenset[date],
        dias_aviso_previo: int,
    ) -> None:
        self._repositorio = repositorio
        self._reloj = reloj
        self._feriados = feriados
        self._dias_aviso_previo = dias_aviso_previo

    async def ejecutar(self) -> list[ControlPeriodoSusalud]:
        hoy = _hoy(self._reloj)
        resumenes = {r.periodo: r for r in await self._repositorio.lotes_por_periodo()}
        if not resumenes:
            return []
        ultimo_cerrado = periodo_de(hoy.replace(day=1) - timedelta(days=1))
        periodo, hasta = min(resumenes), max(max(resumenes), ultimo_cerrado)
        controles: list[ControlPeriodoSusalud] = []
        while periodo <= hasta:
            controles.append(self._control(periodo, resumenes.get(periodo), hoy))
            periodo = periodo_siguiente(periodo)
        return sorted(controles, key=lambda c: c.periodo, reverse=True)

    def _control(
        self, periodo: str, resumen: LotesPeriodo | None, hoy: date
    ) -> ControlPeriodoSusalud:
        limite = fecha_limite_envio_susalud(periodo, self._feriados)
        if resumen is None:
            return ControlPeriodoSusalud(periodo, 0, 0, limite, None, EstadoEnvioSusalud.SIN_LOTES)
        return ControlPeriodoSusalud(
            periodo,
            resumen.lotes,
            resumen.pendientes_envio,
            limite,
            resumen.ultimo_envio,
            self._estado(resumen, limite, hoy),
        )

    def _estado(self, resumen: LotesPeriodo, limite: date, hoy: date) -> EstadoEnvioSusalud:
        if resumen.pendientes_envio == 0 and resumen.ultimo_envio is not None:
            enviado = resumen.ultimo_envio
            if enviado.tzinfo is None:
                enviado = enviado.replace(tzinfo=UTC)
            if enviado.astimezone(ZONA_PERU).date() > limite:
                return EstadoEnvioSusalud.ENVIADO_FUERA_DE_PLAZO
            return EstadoEnvioSusalud.ENVIADO
        if hoy > limite:
            return EstadoEnvioSusalud.VENCIDO
        if (limite - hoy).days <= self._dias_aviso_previo:
            return EstadoEnvioSusalud.POR_VENCER
        return EstadoEnvioSusalud.PENDIENTE


class RevisarPlazoSusalud:
    """Parte del control de plazos que corre el temporizador (CU-11): un
    aviso por lote cerca de la fecha limite y un escalamiento al jefe
    cuando ya vencio, una sola vez cada uno."""

    def __init__(
        self,
        repositorio: RepositorioControlSusalud,
        observabilidad: Observabilidad,
        reloj: Reloj,
        feriados: frozenset[date],
        dias_aviso_previo: int,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._feriados = feriados
        self._dias_aviso_previo = dias_aviso_previo

    async def ejecutar(self) -> ResumenHito:
        hoy = _hoy(self._reloj)
        lotes = await self._repositorio.lotes_pendientes_envio()
        avisados = escalados = 0
        for lote in lotes:
            limite = fecha_limite_envio_susalud(lote.periodo, self._feriados)
            if hoy > limite and not lote.ya_escalado:
                await self._registrar(lote, TIPO_ESCALADO_SUSALUD, limite)
                escalados += 1
            elif 0 <= (limite - hoy).days <= self._dias_aviso_previo and not lote.ya_avisado:
                await self._registrar(lote, TIPO_AVISO_SUSALUD, limite)
                avisados += 1
        return ResumenHito(revisados=len(lotes), avisados=avisados, escalados=escalados)

    async def _registrar(self, lote: LotePendienteSusalud, tipo_evento: str, limite: date) -> None:
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote.lote_id,
                tipo_evento=tipo_evento,
                actor=_ACTOR_TEMPORIZADOR,
                estado_previo=None,
                estado_nuevo=None,
                datos={"periodo": lote.periodo, "fecha_limite": limite.isoformat()},
            )
        )
