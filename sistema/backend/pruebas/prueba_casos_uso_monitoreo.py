"""Pruebas de MonitorearRespuestaIafas (Seccion 8.3, CU-05/RF-07) con dobles
de prueba -- sin Postgres ni HTTP real: eso se verifica aparte, contra el
simulador real en Docker (docs/DECISIONES.md, Fase 12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest

from app.dominio.integracion.casos_uso import (
    MonitorearRespuestaIafas,
    SolicitarMonitoreoRespuestaIafas,
)
from app.dominio.integracion.puertos import (
    ContextoLoteMonitoreo,
    ErrorLoteNoMonitoreable,
    RespuestaReceptor,
)
from app.dominio.puertos_comunes import Evento, MedicionPaso, Observabilidad

_CONTEXTO = ContextoLoteMonitoreo(
    lote_id=1,
    numero="0000001",
    nombre_s01="937_20123456789_12345678_00012_0000001_202609_20260915.S01",
    ventana_monitoreo_horas=48,
)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RepositorioFalso:
    contexto: ContextoLoteMonitoreo | None
    aplicadas: list[tuple[int, str, str | None]] = field(default_factory=list)

    async def obtener_contexto_lote(self, lote_id: int) -> ContextoLoteMonitoreo | None:
        return self.contexto

    async def aplicar_respuesta(
        self, lote_id: int, estado_receptor: str, motivo: str | None, instante: datetime
    ) -> tuple[int, tuple[int, ...]]:
        self.aplicadas.append((lote_id, estado_receptor, motivo))
        return len(self.aplicadas), (10, 11)


@dataclass
class _ConsultorFalso:
    respuesta: RespuestaReceptor | None

    async def consultar(self, nombre_s01: str) -> RespuestaReceptor | None:
        return self.respuesta


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RegistroMedicionesFalso:
    mediciones: list[MedicionPaso] = field(default_factory=list)

    async def registrar(self, medicion: MedicionPaso) -> None:
        self.mediciones.append(medicion)


def _caso_uso(
    contexto: ContextoLoteMonitoreo | None,
    respuesta: RespuestaReceptor | None,
    ahora: datetime,
    registro_eventos: _RegistroEventosFalso | None = None,
    registro_mediciones: _RegistroMedicionesFalso | None = None,
) -> tuple[MonitorearRespuestaIafas, _RepositorioFalso]:
    repositorio = _RepositorioFalso(contexto=contexto)
    caso_uso = MonitorearRespuestaIafas(
        repositorio=repositorio,
        consultor=_ConsultorFalso(respuesta=respuesta),
        observabilidad=Observabilidad(
            eventos=registro_eventos or _RegistroEventosFalso(),
            mediciones=registro_mediciones or _RegistroMedicionesFalso(),
        ),
        reloj=_RelojFijo(ahora),
        intervalo_reconsulta=timedelta(minutes=15),
    )
    return caso_uso, repositorio


@dataclass
class _EstadoLoteFalso:
    estado: str | None

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        return self.estado


@dataclass
class _TrabajosFalso:
    en_curso: bool = False
    encolados: list[tuple[str, dict[str, object], datetime]] = field(default_factory=list)

    async def hay_sin_terminar(self, tipo: str, lote_id: int) -> bool:
        return self.en_curso

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.encolados.append((tipo, carga_util, proximo_intento))
        return 7


def _solicitud(
    estado: str | None, en_curso: bool = False
) -> tuple[SolicitarMonitoreoRespuestaIafas, _TrabajosFalso, _RegistroEventosFalso]:
    trabajos = _TrabajosFalso(en_curso=en_curso)
    eventos = _RegistroEventosFalso()
    caso_uso = SolicitarMonitoreoRespuestaIafas(
        repositorio=_EstadoLoteFalso(estado),  # type: ignore[arg-type]
        repositorio_trabajos=trabajos,  # type: ignore[arg-type]
        observabilidad=Observabilidad(eventos=eventos, mediciones=_RegistroMedicionesFalso()),
        reloj=_RelojFijo(datetime(2026, 9, 20, 10, 0, 0)),
    )
    return caso_uso, trabajos, eventos


async def prueba_solicitar_monitoreo_encola_y_deja_evento() -> None:
    caso_uso, trabajos, eventos = _solicitud("REMITIDO_IAFAS")

    trabajo_id = await caso_uso.ejecutar(lote_id=1, actor="ana.analista")

    assert trabajo_id == 7
    assert trabajos.encolados == [
        (
            "MONITOREAR_RESPUESTA_IAFAS",
            {"lote_id": 1, "usuario_origen": "ana.analista"},
            datetime(2026, 9, 20, 10, 0, 0),
        )
    ]
    assert [(e.tipo_evento, e.lote_id, e.actor) for e in eventos.eventos] == [
        ("LOTE_MONITOREO_SOLICITADO", 1, "ana.analista")
    ]


@pytest.mark.parametrize("estado", [None, "VALIDADO", "ACEPTADO"])
async def prueba_solicitar_monitoreo_rechaza_lote_que_no_esta_remitido(
    estado: str | None,
) -> None:
    caso_uso, trabajos, _ = _solicitud(estado)
    with pytest.raises(ErrorLoteNoMonitoreable):
        await caso_uso.ejecutar(lote_id=1, actor="ana.analista")
    assert trabajos.encolados == []


async def prueba_solicitar_monitoreo_rechaza_si_ya_hay_uno_en_curso() -> None:
    caso_uso, trabajos, eventos = _solicitud("REMITIDO_IAFAS", en_curso=True)
    with pytest.raises(ErrorLoteNoMonitoreable, match="en curso"):
        await caso_uso.ejecutar(lote_id=1, actor="ana.analista")
    assert trabajos.encolados == []
    assert eventos.eventos == []


async def prueba_lote_inexistente_lanza_error() -> None:
    caso_uso, _ = _caso_uso(contexto=None, respuesta=None, ahora=datetime(2026, 9, 18, 10, 0, 0))
    with pytest.raises(ErrorLoteNoMonitoreable):
        await caso_uso.ejecutar(
            lote_id=99, trabajo_creado_en=datetime(2026, 9, 18, 9, 0, 0), actor="trabajador"
        )


async def prueba_sin_respuesta_dentro_de_la_ventana_se_reencola() -> None:
    ahora = datetime(2026, 9, 18, 10, 0, 0)
    creado_en = ahora - timedelta(hours=1)  # muy por debajo de las 48h de ventana
    caso_uso, repositorio = _caso_uso(contexto=_CONTEXTO, respuesta=None, ahora=ahora)

    resultado = await caso_uso.ejecutar(lote_id=1, trabajo_creado_en=creado_en, actor="trabajador")

    assert resultado.resultado == "sin_respuesta"
    assert resultado.proximo_intento == ahora + timedelta(minutes=15)
    assert repositorio.aplicadas == []  # nunca toco datos: no hubo respuesta que aplicar


async def prueba_sin_respuesta_tras_superar_la_ventana_se_agota() -> None:
    ahora = datetime(2026, 9, 20, 11, 0, 0)
    creado_en = ahora - timedelta(hours=49)  # supera las 48h de ventana del contexto
    registro_eventos = _RegistroEventosFalso()
    caso_uso, repositorio = _caso_uso(
        contexto=_CONTEXTO, respuesta=None, ahora=ahora, registro_eventos=registro_eventos
    )

    resultado = await caso_uso.ejecutar(lote_id=1, trabajo_creado_en=creado_en, actor="trabajador")

    assert resultado.resultado == "agotado"
    assert resultado.proximo_intento is None
    assert repositorio.aplicadas == []
    # CU-05: el lote queda senalado como excedido, sin cambiar de estado.
    (evento,) = registro_eventos.eventos
    assert evento.tipo_evento == "LOTE_MONITOREO_EXCEDIDO"
    assert evento.lote_id == 1
    assert evento.estado_nuevo is None


async def prueba_respuesta_aceptado_aplica_y_emite_evento() -> None:
    ahora = datetime(2026, 9, 18, 10, 0, 0)
    registro_eventos = _RegistroEventosFalso()
    caso_uso, repositorio = _caso_uso(
        contexto=_CONTEXTO,
        respuesta=RespuestaReceptor(estado="ACEPTADO", motivo=None),
        ahora=ahora,
        registro_eventos=registro_eventos,
    )

    resultado = await caso_uso.ejecutar(
        lote_id=1,
        trabajo_creado_en=ahora - timedelta(hours=1),
        actor="trabajador",
        usuario_origen="ana.analista",
    )

    assert resultado.resultado == "respondido"
    assert repositorio.aplicadas == [(1, "ACEPTADO", None)]
    assert registro_eventos.eventos[0].tipo_evento == "LOTE_ACEPTADO"
    assert registro_eventos.eventos[0].datos["cuentas_afectadas"] == [10, 11]
    # Control C-07 (Seccion 5.2.7): atribuye al analista que remitio el
    # lote (RemitirLote la propago al encolar este monitoreo).
    assert registro_eventos.eventos[0].usuario_origen == "ana.analista"

    # Fase 25 (T-06, Seccion 5.2.4): ademas del evento del lote, un
    # evento CUENTA_EN_AUDITORIA propio por cada cuenta afectada.
    eventos_cuenta = registro_eventos.eventos[1:]
    assert [e.tipo_evento for e in eventos_cuenta] == ["CUENTA_EN_AUDITORIA"] * 2
    assert [e.cuenta_medica_id for e in eventos_cuenta] == [10, 11]
    assert all(e.estado_previo == "ENVIADA" for e in eventos_cuenta)
    assert all(e.estado_nuevo == "EN_AUDITORIA" for e in eventos_cuenta)
    assert all(e.usuario_origen == "ana.analista" for e in eventos_cuenta)


async def prueba_respuesta_rechazado_aplica_y_emite_evento() -> None:
    ahora = datetime(2026, 9, 18, 10, 0, 0)
    registro_eventos = _RegistroEventosFalso()
    caso_uso, repositorio = _caso_uso(
        contexto=_CONTEXTO,
        respuesta=RespuestaReceptor(estado="RECHAZADO", motivo="estructura invalida"),
        ahora=ahora,
        registro_eventos=registro_eventos,
    )

    resultado = await caso_uso.ejecutar(
        lote_id=1, trabajo_creado_en=ahora - timedelta(hours=1), actor="trabajador"
    )

    assert resultado.resultado == "respondido"
    assert repositorio.aplicadas == [(1, "RECHAZADO", "estructura invalida")]
    assert registro_eventos.eventos[0].tipo_evento == "LOTE_RECHAZADO"
    assert registro_eventos.eventos[0].datos["motivo"] == "estructura invalida"
    assert registro_eventos.eventos[0].estado_previo == "REMITIDO_IAFAS"

    # T-04 (Seccion 5.2.4, RF-16/RT-01): un evento propio por cada cuenta
    # rechazada, con el motivo del receptor.
    eventos_cuenta = registro_eventos.eventos[1:]
    assert [e.tipo_evento for e in eventos_cuenta] == ["CUENTA_RECHAZADA"] * 2
    assert [e.cuenta_medica_id for e in eventos_cuenta] == [10, 11]
    assert all(e.estado_previo == "ENVIADA" for e in eventos_cuenta)
    assert all(e.estado_nuevo == "RECHAZADA" for e in eventos_cuenta)
    assert all(e.datos["motivo"] == "estructura invalida" for e in eventos_cuenta)


async def prueba_cada_desenlace_registra_una_medicion_de_paso() -> None:
    """Seccion 6.4 / evidencia_mediciones_pasos.csv (Fase 20): el
    monitoreo de respuesta es uno de los pasos automatizados que debe
    emitir una fila en medicion_paso, con las tres resultado posibles."""

    ahora = datetime(2026, 9, 18, 10, 0, 0)

    mediciones_respondido = _RegistroMedicionesFalso()
    caso_uso, _ = _caso_uso(
        contexto=_CONTEXTO,
        respuesta=RespuestaReceptor(estado="ACEPTADO", motivo=None),
        ahora=ahora,
        registro_mediciones=mediciones_respondido,
    )
    await caso_uso.ejecutar(lote_id=1, trabajo_creado_en=ahora - timedelta(hours=1), actor="x")
    assert len(mediciones_respondido.mediciones) == 1
    assert mediciones_respondido.mediciones[0].paso == "monitoreo_respuesta_iafas"
    assert mediciones_respondido.mediciones[0].resultado == "respondido"
    assert mediciones_respondido.mediciones[0].lote_id == 1

    mediciones_sin_respuesta = _RegistroMedicionesFalso()
    caso_uso, _ = _caso_uso(
        contexto=_CONTEXTO,
        respuesta=None,
        ahora=ahora,
        registro_mediciones=mediciones_sin_respuesta,
    )
    await caso_uso.ejecutar(lote_id=1, trabajo_creado_en=ahora - timedelta(hours=1), actor="x")
    assert mediciones_sin_respuesta.mediciones[0].resultado == "sin_respuesta"

    mediciones_agotado = _RegistroMedicionesFalso()
    caso_uso, _ = _caso_uso(
        contexto=_CONTEXTO, respuesta=None, ahora=ahora, registro_mediciones=mediciones_agotado
    )
    await caso_uso.ejecutar(lote_id=1, trabajo_creado_en=ahora - timedelta(hours=49), actor="x")
    assert mediciones_agotado.mediciones[0].resultado == "agotado"
