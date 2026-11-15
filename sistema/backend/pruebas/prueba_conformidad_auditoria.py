"""Pruebas de CU-07, la conformidad de la auditoria (resultado sin
observaciones): validaciones del caso de uso con dobles y la lectura de la
conformidad vigente contra SQLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.observaciones.conformidad import (
    TIPO_EVENTO_CONFORMIDAD,
    ErrorConformidadYaRegistrada,
    ErrorCuentaInexistenteAuditoria,
    ErrorCuentaSinAuditoriaEnCurso,
    RegistrarConformidadAuditoria,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.repositorio_conformidad_auditoria_sql import (
    RepositorioConformidadAuditoriaSql,
)
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql
from pruebas.prueba_repositorio_plazos import (
    _AHORA,
    _insertar_evento,
    _sembrar_cuenta,
    _sembrar_iafas,
)


@dataclass
class _EstadoFijo:
    estado: str | None

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estado

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        raise AssertionError("la conformidad no cambia el estado de la cuenta")


@dataclass
class _ConformidadFija:
    vigente: datetime | None = None

    async def conformidad_vigente(self, cuenta_medica_id: int) -> datetime | None:
        return self.vigente


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@pytest.mark.parametrize("estado", ["EN_AUDITORIA", "SUBSANADA"])
async def prueba_conformidad_registra_el_evento_sin_cambiar_el_estado(estado: str) -> None:
    registro = _RegistroEventosFalso()
    caso_uso = RegistrarConformidadAuditoria(_EstadoFijo(estado), _ConformidadFija(), registro)

    await caso_uso.ejecutar(5, actor="ana.analista")

    (evento,) = registro.eventos
    assert evento.tipo_evento == TIPO_EVENTO_CONFORMIDAD
    assert evento.cuenta_medica_id == 5
    assert evento.estado_previo is None and evento.estado_nuevo is None
    assert evento.datos == {"estado_cuenta": estado}


@pytest.mark.parametrize("estado", ["FACTURADA", "ENVIADA", "GLOSADA", "LIQUIDADA", "CERRADA"])
async def prueba_conformidad_exige_una_auditoria_en_curso(estado: str) -> None:
    caso_uso = RegistrarConformidadAuditoria(
        _EstadoFijo(estado), _ConformidadFija(), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorCuentaSinAuditoriaEnCurso):
        await caso_uso.ejecutar(5, actor="ana.analista")


async def prueba_conformidad_no_se_registra_dos_veces() -> None:
    caso_uso = RegistrarConformidadAuditoria(
        _EstadoFijo("EN_AUDITORIA"), _ConformidadFija(_AHORA), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorConformidadYaRegistrada):
        await caso_uso.ejecutar(5, actor="ana.analista")


async def prueba_conformidad_de_cuenta_inexistente() -> None:
    caso_uso = RegistrarConformidadAuditoria(
        _EstadoFijo(None), _ConformidadFija(), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorCuentaInexistenteAuditoria):
        await caso_uso.ejecutar(5, actor="ana.analista")


async def prueba_conformidad_vigente_y_fin_del_plazo_de_auditoria(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=21,
            dias_plazo_pago_liquidacion=30,
        )
        conforme = await _sembrar_cuenta(sesion, iafas_id, "EN_AUDITORIA")
        pendiente = await _sembrar_cuenta(sesion, iafas_id, "EN_AUDITORIA")
        inicio = _AHORA - timedelta(days=10)
        for cuenta in (conforme, pendiente):
            await _insertar_evento(sesion, cuenta, "INICIO_AUDITORIA", "EN_AUDITORIA", inicio)
        await _insertar_evento(
            sesion, conforme, TIPO_EVENTO_CONFORMIDAD, None, inicio + timedelta(days=2)
        )
        await sesion.commit()

        conformidades = RepositorioConformidadAuditoriaSql(sesion)
        assert await conformidades.conformidad_vigente(conforme) == inicio + timedelta(days=2)
        assert await conformidades.conformidad_vigente(pendiente) is None

        hitos = await RepositorioPlazosSql(sesion, 5).cuentas_en_auditoria()
        assert {h.cuenta_medica_id for h in hitos} == {pendiente}


async def prueba_conformidad_anterior_al_estado_actual_no_es_vigente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=21,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta = await _sembrar_cuenta(sesion, iafas_id, "SUBSANADA")
        inicio = _AHORA - timedelta(days=10)
        await _insertar_evento(sesion, cuenta, "INICIO_AUDITORIA", "EN_AUDITORIA", inicio)
        await _insertar_evento(
            sesion, cuenta, TIPO_EVENTO_CONFORMIDAD, None, inicio + timedelta(days=1)
        )
        await _insertar_evento(
            sesion, cuenta, "SUBSANACION", "SUBSANADA", inicio + timedelta(days=5)
        )
        await sesion.commit()

        conformidades = RepositorioConformidadAuditoriaSql(sesion)
        assert await conformidades.conformidad_vigente(cuenta) is None
