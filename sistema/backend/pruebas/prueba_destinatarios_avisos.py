"""Quien ve los avisos de una observacion (2026-11-19): con persona
asignada, esa persona y la jefatura; sin ella, el reparto por rol. La falla
de la entrega de una respuesta tambien sigue a la observacion."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.avisos.casos_uso import ListarAvisos
from app.dominio.avisos.destinatarios import es_destinatario, tipos_a_consultar
from app.dominio.avisos.valores import EventoAviso
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_observaciones import ObservacionModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_avisos_sql import RepositorioAvisosSql
from pruebas.prueba_repositorio_observaciones import _sembrar_cuenta, _sembrar_motivo

_ANALISTA = frozenset({NombreRol.ANALISTA})
_AUDITOR = frozenset({NombreRol.AUDITOR})
_JEFE = frozenset({NombreRol.JEFE, NombreRol.TESORERIA, NombreRol.GERENTE})
_ADMINISTRADOR = frozenset({NombreRol.ADMINISTRADOR})


def _aviso(tipo: str, asignado: int | None = None, **datos: Any) -> EventoAviso:
    return EventoAviso(
        evento_id=f"{tipo}-{asignado}",
        tipo_evento=tipo,
        ocurrido_en=datetime(2026, 11, 19, 8, 0, 0),
        datos={"observacion_id": 3, **datos},
        cuenta_medica_id=5,
        identificacion_interna="CTA0000005",
        lote_id=None,
        numero_lote=None,
        responsable_usuario_id=asignado,
        responsable_rol="analista",
    )


def prueba_con_persona_asignada_lo_ven_ella_y_el_jefe() -> None:
    for tipo in (
        "OBSERVACION_REASIGNADA",
        "OBSERVACION_PLAZO_PROXIMO_A_VENCER",
        "OBSERVACION_PLAZO_VENCIDO_ESCALADO",
    ):
        aviso = _aviso(tipo, asignado=7)
        assert es_destinatario(aviso, _ANALISTA, 7)
        assert not es_destinatario(aviso, _ANALISTA, 8)
        assert not es_destinatario(aviso, _AUDITOR, 9)
        assert es_destinatario(aviso, _JEFE, 1)


def prueba_sin_persona_asignada_rige_el_reparto_por_rol() -> None:
    proximo = _aviso("OBSERVACION_PLAZO_PROXIMO_A_VENCER")
    assert es_destinatario(proximo, _ANALISTA, 8)
    assert es_destinatario(proximo, _AUDITOR, 9)
    assert not es_destinatario(proximo, _JEFE, 1)
    assert es_destinatario(_aviso("OBSERVACION_PLAZO_VENCIDO_ESCALADO"), _JEFE, 1)


def prueba_la_entrega_agotada_va_al_responsable_jefe_y_administrador() -> None:
    asignada = _aviso("TRABAJO_AGOTADO", 7, tipo_trabajo="ENVIAR_RESPUESTA_IAFAS")
    assert es_destinatario(asignada, _AUDITOR, 7)
    assert not es_destinatario(asignada, _ANALISTA, 8)
    assert es_destinatario(asignada, _JEFE, 1)
    assert es_destinatario(asignada, _ADMINISTRADOR, 2)
    # Sin persona: el rol responsable de la observacion, ademas del catalogo.
    tecnica = replace(
        _aviso("TRABAJO_AGOTADO", tipo_trabajo="ENVIAR_RESPUESTA_IAFAS"),
        responsable_rol="auditor",
    )
    assert es_destinatario(tecnica, _AUDITOR, 9)


def prueba_los_demas_avisos_siguen_por_rol() -> None:
    cobertura = _aviso("TRABAJO_AGOTADO", tipo_trabajo="CONSULTAR_COBERTURA")
    assert not es_destinatario(cobertura, _AUDITOR, 9)
    assert es_destinatario(cobertura, _ANALISTA, 8)
    assert es_destinatario(_aviso("RUPTURA_CADENA_DETECTADA"), _ADMINISTRADOR, 2)
    assert tipos_a_consultar(frozenset({NombreRol.GERENTE})) == []


class _Repositorio:
    def __init__(self, avisos: list[EventoAviso]) -> None:
        self._avisos = avisos

    async def listar(self, tipos_evento: list[str], limite: int) -> list[EventoAviso]:
        return [a for a in self._avisos if a.tipo_evento in tipos_evento]

    async def evaluar_atencion(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        return avisos


async def prueba_la_bandeja_filtra_por_persona() -> None:
    repositorio = _Repositorio([_aviso("OBSERVACION_REASIGNADA", asignado=7)])

    propios = await ListarAvisos(repositorio).ejecutar(_ANALISTA, 10, usuario_id=7)
    ajenos = await ListarAvisos(repositorio).ejecutar(_ANALISTA, 10, usuario_id=8)

    assert [a.tipo_evento for a in propios] == ["OBSERVACION_REASIGNADA"]
    assert ajenos == []


async def prueba_el_repositorio_resuelve_el_responsable(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        await _sembrar_motivo(sesion)
        observacion = ObservacionModelo(
            cuenta_medica_id=cuenta_id,
            motivo_codigo="OBS-01",
            naturaleza="ADMINISTRATIVA",
            es_parcial=False,
            responsable_rol="analista",
            estado="ABIERTA",
            registrado_en=datetime(2026, 11, 19, 8, 0, 0),
        )
        sesion.add(observacion)
        await sesion.flush()
        registro = RegistroEventosSql(sesion)
        for tipo, datos in (
            ("OBSERVACION_PLAZO_PROXIMO_A_VENCER", {"plazo_dias": 15}),
            (
                "OBSERVACION_REASIGNADA",
                {"responsable_usuario_id": 4, "responsable_rol": "analista"},
            ),
        ):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=cuenta_id,
                    tipo_evento=tipo,
                    actor="sistema",
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"observacion_id": observacion.id, **datos},
                )
            )
        avisos = await RepositorioAvisosSql(sesion).listar(
            ["OBSERVACION_PLAZO_PROXIMO_A_VENCER", "OBSERVACION_REASIGNADA"], 10
        )

    por_tipo = {a.tipo_evento: a for a in avisos}
    # El plazo sigue al responsable actual (sin persona); la reasignacion,
    # a quien se asigno.
    assert por_tipo["OBSERVACION_PLAZO_PROXIMO_A_VENCER"].responsable_usuario_id is None
    assert por_tipo["OBSERVACION_PLAZO_PROXIMO_A_VENCER"].responsable_rol == "analista"
    assert por_tipo["OBSERVACION_REASIGNADA"].responsable_usuario_id == 4
