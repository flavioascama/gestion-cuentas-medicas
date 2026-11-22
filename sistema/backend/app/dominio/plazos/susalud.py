"""Control del envio a SUSALUD (RT-05, RI-16): "remitir a SUSALUD dentro
de los diez dias habiles del mes siguiente", con la fecha de envio, el
control de ese plazo y la identificacion de los meses sin lotes.

Hasta la verificacion de cumplimiento del 2026-11-12 solo se registraba la
fecha de envio (`lote_facturacion.enviado_susalud_en`). Aqui se calcula,
por periodo de facturacion, la fecha limite y el estado del envio, y el
temporizador avisa por cada lote que sigue sin enviarse cerca o despues de
esa fecha.

Dias habiles: lunes a viernes, menos los feriados configurados (FERIADOS).
El mes de diciembre vence el ultimo dia habil de enero (Resolucion
043-2025-SUSALUD/S), no a los diez dias habiles.
Sin feriados configurados la fecha limite calculada nunca es posterior a
la real (a lo sumo es anterior): el control avisa antes, nunca despues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from app.compartido.fecha_peru import ZONA_PERU, fecha_peru
from app.dominio.plazos.valores import ResumenHito
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

DIAS_HABILES_ENVIO_SUSALUD = 10
# El Peru no aplica horario de verano: UTC-5 todo el anio.
_ACTOR_TEMPORIZADOR = "temporizador_sistema"
TIPO_AVISO_SUSALUD = "SUSALUD_ENVIO_PROXIMO_A_VENCER"
TIPO_ESCALADO_SUSALUD = "SUSALUD_ENVIO_VENCIDO_ESCALADO"


def periodo_siguiente(periodo: str) -> str:
    anio, mes = int(periodo[:4]), int(periodo[4:6])
    return f"{anio + mes // 12:04d}{mes % 12 + 1:02d}"


def periodo_de(fecha: date) -> str:
    return f"{fecha.year:04d}{fecha.month:02d}"


def _ultimo_dia_habil_de_enero(anio: int, feriados: frozenset[date]) -> date:
    dia = date(anio, 1, 31)
    while dia.weekday() >= 5 or dia in feriados:
        dia -= timedelta(days=1)
    return dia


def fecha_limite_envio_susalud(periodo: str, feriados: frozenset[date]) -> date:
    """Decimo dia habil del mes siguiente al periodo facturado; para
    diciembre, el ultimo dia habil de enero del anio siguiente."""
    if periodo[4:6] == "12":
        anio = int(periodo_siguiente(periodo)[:4])
        return _ultimo_dia_habil_de_enero(anio, feriados)
    return fecha_limite_declaracion_susalud(periodo, feriados)


def fecha_limite_declaracion_susalud(periodo: str, feriados: frozenset[date]) -> date:
    """Declaracion del mes sin facturacion: decimo dia habil del mes
    siguiente, tambien para diciembre (el articulo 9 solo da la
    excepcion de diciembre al envio de informacion)."""
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
    # Los que el envio tomaria ahora: remitidos a la IAFAS, sin enviar.
    # Un lote aun sin remitir (o rechazado) es pendiente, pero no esta listo.
    listos_envio: int = 0


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
    listos_envio: int = 0
    # Solo en los meses sin lotes: cuando se registro la declaracion jurada.
    declarada_en: datetime | None = None
    declarada_fuera_de_plazo: bool = False


class RepositorioControlSusalud(Protocol):
    async def lotes_por_periodo(self) -> list[LotesPeriodo]:
        """Un resumen por cada periodo que tiene al menos un lote."""
        ...

    async def lotes_pendientes_envio(self) -> list[LotePendienteSusalud]:
        """Lotes sujetos a envio que aun no se enviaron a SUSALUD."""
        ...

    async def declaraciones(self) -> dict[str, datetime]:
        """Periodo -> cuando se registro su declaracion jurada."""
        ...

    async def avisos_sin_lotes(self) -> dict[str, frozenset[str]]:
        """Periodo sin lotes -> tipos de aviso ya registrados."""
        ...

    async def registrar_declaracion(self, periodo: str, registrada_por: str) -> datetime:
        """Guarda la declaracion y devuelve cuando se registro."""
        ...


def _hoy(reloj: Reloj) -> date:
    ahora = reloj.ahora()
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=UTC)
    return ahora.astimezone(ZONA_PERU).date()


def periodos_a_controlar(con_lotes: set[str], hoy: date) -> list[str]:
    """Del primer periodo con lotes al ultimo mes cerrado, sin huecos."""
    if not con_lotes:
        return []
    ultimo_cerrado = periodo_de(hoy.replace(day=1) - timedelta(days=1))
    periodo, hasta = min(con_lotes), max(max(con_lotes), ultimo_cerrado)
    periodos: list[str] = []
    while periodo <= hasta:
        periodos.append(periodo)
        periodo = periodo_siguiente(periodo)
    return periodos


def estado_por_plazo(limite: date, hoy: date, dias_aviso_previo: int) -> EstadoEnvioSusalud:
    if hoy > limite:
        return EstadoEnvioSusalud.VENCIDO
    if (limite - hoy).days <= dias_aviso_previo:
        return EstadoEnvioSusalud.POR_VENCER
    return EstadoEnvioSusalud.PENDIENTE


class ConsultarControlSusalud:
    """Un renglon por periodo, desde el primero con lotes hasta el ultimo
    mes cerrado. Un mes sin lotes pide la declaracion jurada: corre el mismo
    plazo que un reporte pendiente y, ya declarado, queda SIN_LOTES."""

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
        declaradas = await self._repositorio.declaraciones()
        controles = [
            self._control(periodo, resumenes.get(periodo), hoy, declaradas.get(periodo))
            for periodo in periodos_a_controlar(set(resumenes), hoy)
        ]
        return sorted(controles, key=lambda c: c.periodo, reverse=True)

    def _control(
        self, periodo: str, resumen: LotesPeriodo | None, hoy: date, declarada: datetime | None
    ) -> ControlPeriodoSusalud:
        if resumen is None:
            limite = fecha_limite_declaracion_susalud(periodo, self._feriados)
        else:
            limite = fecha_limite_envio_susalud(periodo, self._feriados)
        if resumen is None and declarada is not None:
            return ControlPeriodoSusalud(
                periodo,
                0,
                0,
                limite,
                None,
                EstadoEnvioSusalud.SIN_LOTES,
                declarada_en=declarada,
                declarada_fuera_de_plazo=fecha_peru(declarada) > limite,
            )
        if resumen is None:
            estado = estado_por_plazo(limite, hoy, self._dias_aviso_previo)
            return ControlPeriodoSusalud(periodo, 0, 0, limite, None, estado)
        return ControlPeriodoSusalud(
            periodo,
            resumen.lotes,
            resumen.pendientes_envio,
            limite,
            resumen.ultimo_envio,
            self._estado(resumen, limite, hoy),
            resumen.listos_envio,
        )

    def _estado(self, resumen: LotesPeriodo, limite: date, hoy: date) -> EstadoEnvioSusalud:
        if resumen.pendientes_envio == 0 and resumen.ultimo_envio is not None:
            enviado = resumen.ultimo_envio
            if enviado.tzinfo is None:
                enviado = enviado.replace(tzinfo=UTC)
            if enviado.astimezone(ZONA_PERU).date() > limite:
                return EstadoEnvioSusalud.ENVIADO_FUERA_DE_PLAZO
            return EstadoEnvioSusalud.ENVIADO
        return estado_por_plazo(limite, hoy, self._dias_aviso_previo)


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
            tipo = self._tipo_a_registrar(limite, hoy, lote.ya_avisado, lote.ya_escalado)
            if tipo is not None:
                await self._registrar(tipo, lote.periodo, limite, lote.lote_id)
                avisados += tipo == TIPO_AVISO_SUSALUD
                escalados += tipo == TIPO_ESCALADO_SUSALUD
        sin_declarar = await self._periodos_sin_declarar(hoy)
        for periodo, avisos in sin_declarar:
            limite = fecha_limite_declaracion_susalud(periodo, self._feriados)
            tipo = self._tipo_a_registrar(
                limite, hoy, TIPO_AVISO_SUSALUD in avisos, TIPO_ESCALADO_SUSALUD in avisos
            )
            if tipo is not None:
                await self._registrar(tipo, periodo, limite, None)
                avisados += tipo == TIPO_AVISO_SUSALUD
                escalados += tipo == TIPO_ESCALADO_SUSALUD
        return ResumenHito(
            revisados=len(lotes) + len(sin_declarar), avisados=avisados, escalados=escalados
        )

    def _tipo_a_registrar(
        self, limite: date, hoy: date, ya_avisado: bool, ya_escalado: bool
    ) -> str | None:
        if hoy > limite:
            return None if ya_escalado else TIPO_ESCALADO_SUSALUD
        if (limite - hoy).days <= self._dias_aviso_previo and not ya_avisado:
            return TIPO_AVISO_SUSALUD
        return None

    async def _periodos_sin_declarar(self, hoy: date) -> list[tuple[str, frozenset[str]]]:
        """Meses cerrados sin lotes y sin declaracion jurada, con los avisos
        que ya se registraron de cada uno."""
        con_lotes = {r.periodo for r in await self._repositorio.lotes_por_periodo()}
        declaradas = await self._repositorio.declaraciones()
        avisos = await self._repositorio.avisos_sin_lotes()
        return [
            (periodo, avisos.get(periodo, frozenset()))
            for periodo in periodos_a_controlar(con_lotes, hoy)
            if periodo not in con_lotes and periodo not in declaradas
        ]

    async def _registrar(
        self, tipo_evento: str, periodo: str, limite: date, lote_id: int | None
    ) -> None:
        # Un mes sin lotes no tiene lote ni cuenta: el evento se guarda bajo
        # el agregado de sesion de usuario con el periodo como identificador.
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                sesion_usuario_id=None if lote_id is not None else int(periodo),
                tipo_evento=tipo_evento,
                actor=_ACTOR_TEMPORIZADOR,
                estado_previo=None,
                estado_nuevo=None,
                datos={"periodo": periodo, "fecha_limite": limite.isoformat()},
            )
        )
