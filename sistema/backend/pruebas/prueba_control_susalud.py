"""Pruebas del control de envio a SUSALUD (RT-05, RI-16): la fecha limite
de los diez dias habiles, el estado de cada periodo (incluidos los meses
sin lotes), los avisos del temporizador y el adaptador SQL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.plazos.susalud import (
    TIPO_AVISO_SUSALUD,
    TIPO_ESCALADO_SUSALUD,
    ConsultarControlSusalud,
    EstadoEnvioSusalud,
    LotePendienteSusalud,
    LotesPeriodo,
    RevisarPlazoSusalud,
    fecha_limite_envio_susalud,
)
from app.dominio.puertos_comunes import Evento, Observabilidad
from app.infraestructura.persistencia.modelos_integracion import (
    IafasModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_control_susalud_sql import (
    RepositorioControlSusaludSql,
)

# 13/11/2026 10:00 en Lima.
_AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


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
class _RepositorioFalso:
    periodos: list[LotesPeriodo] = field(default_factory=list)
    pendientes: list[LotePendienteSusalud] = field(default_factory=list)

    async def lotes_por_periodo(self) -> list[LotesPeriodo]:
        return self.periodos

    async def lotes_pendientes_envio(self) -> list[LotePendienteSusalud]:
        return self.pendientes


# --- fecha limite ---------------------------------------------------------


def prueba_fecha_limite_es_el_decimo_dia_habil_del_mes_siguiente() -> None:
    # Noviembre de 2026 empieza en domingo: del lunes 2 al viernes 13.
    assert fecha_limite_envio_susalud("202610", frozenset()) == date(2026, 11, 13)


def prueba_fecha_limite_descuenta_los_feriados_configurados() -> None:
    feriados = frozenset({date(2026, 11, 2)})
    assert fecha_limite_envio_susalud("202610", feriados) == date(2026, 11, 16)


def prueba_fecha_limite_de_diciembre_cae_en_enero_del_anio_siguiente() -> None:
    assert fecha_limite_envio_susalud("202612", frozenset()) == date(2027, 1, 14)
    assert fecha_limite_envio_susalud("202612", frozenset({date(2027, 1, 1)})) == date(2027, 1, 15)


# --- ConsultarControlSusalud ----------------------------------------------


async def prueba_control_marca_estados_y_meses_sin_lotes() -> None:
    repositorio = _RepositorioFalso(
        periodos=[
            # Limite 14/08: enviado el 20/08.
            LotesPeriodo("202607", 2, 0, datetime(2026, 8, 20, 15, 0, tzinfo=UTC)),
            # Limite 14/09: enviado el 05/09.
            LotesPeriodo("202608", 1, 0, datetime(2026, 9, 5, 15, 0, tzinfo=UTC)),
            # 202609 sin ningun lote. Limite de 202610: 13/11 (hoy).
            # Dos pendientes; solo uno ya esta validado y se puede enviar.
            LotesPeriodo("202610", 3, 2, None, listos_envio=1),
        ]
    )
    controles = await ConsultarControlSusalud(
        repositorio, _RelojFijo(), frozenset(), dias_aviso_previo=2
    ).ejecutar()

    assert [(c.periodo, c.estado) for c in controles] == [
        ("202610", EstadoEnvioSusalud.POR_VENCER),
        ("202609", EstadoEnvioSusalud.SIN_LOTES),
        ("202608", EstadoEnvioSusalud.ENVIADO),
        ("202607", EstadoEnvioSusalud.ENVIADO_FUERA_DE_PLAZO),
    ]
    assert controles[0].pendientes_envio == 2
    assert controles[1].fecha_limite == date(2026, 10, 14)
    # El boton de envio se habilita con este dato: solo 202610 tiene algo listo.
    assert [c.listos_envio for c in controles] == [1, 0, 0, 0]


async def prueba_control_incluye_hasta_el_ultimo_mes_cerrado() -> None:
    repositorio = _RepositorioFalso(periodos=[LotesPeriodo("202608", 1, 1, None)])
    controles = await ConsultarControlSusalud(
        repositorio, _RelojFijo(), frozenset(), dias_aviso_previo=2
    ).ejecutar()

    assert [c.periodo for c in controles] == ["202610", "202609", "202608"]
    assert controles[0].estado == EstadoEnvioSusalud.SIN_LOTES
    assert controles[2].estado == EstadoEnvioSusalud.VENCIDO


async def prueba_control_sin_lotes_no_inventa_periodos() -> None:
    controles = await ConsultarControlSusalud(
        _RepositorioFalso(), _RelojFijo(), frozenset(), dias_aviso_previo=2
    ).ejecutar()
    assert controles == []


# --- RevisarPlazoSusalud --------------------------------------------------


async def prueba_revision_avisa_y_escala_una_sola_vez_por_lote() -> None:
    registro = _RegistroEventosFalso()
    repositorio = _RepositorioFalso(
        pendientes=[
            LotePendienteSusalud(1, "202609", ya_avisado=True, ya_escalado=False),
            LotePendienteSusalud(2, "202610", ya_avisado=False, ya_escalado=False),
            LotePendienteSusalud(3, "202610", ya_avisado=True, ya_escalado=False),
            LotePendienteSusalud(4, "202609", ya_avisado=True, ya_escalado=True),
        ]
    )
    resumen = await RevisarPlazoSusalud(
        repositorio,
        Observabilidad(eventos=registro, mediciones=_MedicionesFalso()),
        _RelojFijo(),
        frozenset(),
        dias_aviso_previo=2,
    ).ejecutar()

    assert (resumen.revisados, resumen.avisados, resumen.escalados) == (4, 1, 1)
    assert [(e.lote_id, e.tipo_evento) for e in registro.eventos] == [
        (1, TIPO_ESCALADO_SUSALUD),
        (2, TIPO_AVISO_SUSALUD),
    ]
    assert registro.eventos[0].datos == {"periodo": "202609", "fecha_limite": "2026-10-14"}
    assert all(e.cuenta_medica_id is None for e in registro.eventos)


# --- RepositorioControlSusaludSql -----------------------------------------


async def _sembrar_lote(
    sesion: AsyncSession, iafas_id: int, periodo: str, estado: str, enviado: datetime | None
) -> int:
    lote = LoteFacturacionModelo(
        numero=uuid.uuid4().hex[:7],
        iafas_id=iafas_id,
        periodo=periodo,
        generado_en=_AHORA,
        estado=estado,
        enviado_susalud_en=enviado,
    )
    sesion.add(lote)
    await sesion.flush()
    return lote.id


async def prueba_repositorio_resume_periodos_y_pendientes(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas = IafasModelo(
            codigo=uuid.uuid4().hex[:5],
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=7,
            ventana_monitoreo_horas=48,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        sesion.add(iafas)
        await sesion.flush()
        enviado = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
        await _sembrar_lote(sesion, iafas.id, "202608", "ACEPTADO", enviado)
        avisado = await _sembrar_lote(sesion, iafas.id, "202610", "VALIDADO", None)
        pendiente = await _sembrar_lote(sesion, iafas.id, "202610", "GENERADO", None)
        await _sembrar_lote(sesion, iafas.id, "202610", "OBSERVADO_VALIDADOR", None)
        await RegistroEventosSql(sesion).registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=avisado,
                tipo_evento=TIPO_AVISO_SUSALUD,
                actor="temporizador_sistema",
                estado_previo=None,
                estado_nuevo=None,
            )
        )

        repositorio = RepositorioControlSusaludSql(sesion)
        periodos = {p.periodo: p for p in await repositorio.lotes_por_periodo()}
        assert periodos["202608"].lotes == 1
        assert periodos["202608"].pendientes_envio == 0
        assert periodos["202608"].ultimo_envio is not None
        # Aceptado y ya enviado: nada queda listo para enviar.
        assert periodos["202608"].listos_envio == 0
        assert periodos["202610"].lotes == 3
        assert periodos["202610"].pendientes_envio == 2
        # De los dos pendientes, el GENERADO aun no esta validado.
        assert periodos["202610"].listos_envio == 1

        pendientes = {p.lote_id: p for p in await repositorio.lotes_pendientes_envio()}
        assert set(pendientes) >= {avisado, pendiente}
        assert pendientes[avisado].ya_avisado is True
        assert pendientes[pendiente].ya_avisado is False
