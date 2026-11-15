"""Pruebas de la administracion de parametros por IAFAS (CU-18) y de la
carga del catalogo GTIN desde la pantalla de administracion."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.farmacia.casos_uso import CargarCatalogoGtin
from app.dominio.farmacia.puertos import VersionCatalogoGtin
from app.dominio.plazos.parametros import (
    ActualizarParametrosIafas,
    ErrorIafasInexistente,
    ErrorParametroInvalido,
    ParametrosIafas,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.repositorio_parametros_iafas_sql import (
    RepositorioParametrosIafasSql,
)
from pruebas.prueba_repositorio_plazos import _sembrar_iafas

_IAFAS = ParametrosIafas(
    iafas_id=3,
    codigo="00012",
    razon_social="IAFAS de prueba",
    periodicidad_remision_dias=7,
    ventana_monitoreo_horas=48,
    dias_plazo_respuesta_observacion=7,
    dias_plazo_comunicacion_auditoria=30,
    dias_plazo_pago_liquidacion=30,
)


@dataclass
class _RepositorioFalso:
    actual: ParametrosIafas | None = _IAFAS
    actualizaciones: list[dict[str, int]] = field(default_factory=list)

    async def listar(self) -> list[ParametrosIafas]:
        return [self.actual] if self.actual else []

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None:
        return self.actual

    async def actualizar(self, iafas_id: int, cambios: dict[str, int]) -> ParametrosIafas:
        assert self.actual is not None
        self.actualizaciones.append(cambios)
        self.actual = replace(self.actual, **cambios)
        return self.actual


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


async def prueba_actualizar_registra_solo_lo_que_cambio() -> None:
    repositorio, registro = _RepositorioFalso(), _RegistroEventosFalso()
    caso_uso = ActualizarParametrosIafas(repositorio, registro)

    resultado = await caso_uso.ejecutar(
        3,
        {"dias_plazo_pago_liquidacion": 45, "ventana_monitoreo_horas": 48},
        actor="admin.prueba",
        usuario_id=9,
    )

    assert resultado.dias_plazo_pago_liquidacion == 45
    assert repositorio.actualizaciones == [{"dias_plazo_pago_liquidacion": 45}]
    (evento,) = registro.eventos
    assert evento.tipo_evento == "PARAMETROS_IAFAS_ACTUALIZADOS"
    assert evento.sesion_usuario_id == 9
    assert evento.datos == {
        "iafas_codigo": "00012",
        "cambios": {"dias_plazo_pago_liquidacion": {"antes": 30, "despues": 45}},
    }


async def prueba_sin_cambios_no_registra_nada() -> None:
    registro = _RegistroEventosFalso()
    await ActualizarParametrosIafas(_RepositorioFalso(), registro).ejecutar(
        3, {"dias_plazo_pago_liquidacion": 30}, actor="admin.prueba", usuario_id=9
    )
    assert registro.eventos == []


@pytest.mark.parametrize(
    "cambios", [{"dias_plazo_pago_liquidacion": 0}, {"ventana_monitoreo_horas": 400}, {"otro": 3}]
)
async def prueba_rechaza_valores_fuera_de_rango(cambios: dict[str, int]) -> None:
    caso_uso = ActualizarParametrosIafas(_RepositorioFalso(), _RegistroEventosFalso())
    with pytest.raises(ErrorParametroInvalido):
        await caso_uso.ejecutar(3, cambios, actor="admin.prueba", usuario_id=9)


async def prueba_iafas_inexistente() -> None:
    caso_uso = ActualizarParametrosIafas(_RepositorioFalso(None), _RegistroEventosFalso())
    with pytest.raises(ErrorIafasInexistente):
        await caso_uso.ejecutar(3, {"dias_plazo_pago_liquidacion": 10}, "admin.prueba", 9)


async def prueba_repositorio_actualiza_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        repositorio = RepositorioParametrosIafasSql(sesion)
        actualizados = await repositorio.actualizar(iafas_id, {"dias_plazo_pago_liquidacion": 20})
        assert actualizados.dias_plazo_pago_liquidacion == 20
        assert any(p.iafas_id == iafas_id for p in await repositorio.listar())


class _CargadorFalso:
    async def cargar(self) -> VersionCatalogoGtin:
        return VersionCatalogoGtin(
            id=5, ruta_origen="catalogo_gtin.yaml", conteo=19, cargado_en=datetime(2026, 11, 13)
        )


async def prueba_cargar_catalogo_gtin_queda_en_la_bitacora() -> None:
    registro = _RegistroEventosFalso()
    version = await CargarCatalogoGtin(_CargadorFalso(), registro).ejecutar("admin.prueba", 9)

    assert version.id == 5
    (evento,) = registro.eventos
    assert evento.tipo_evento == "CATALOGO_GTIN_CARGADO"
    assert evento.sesion_usuario_id == 9
    assert evento.datos == {"version_id": 5, "conteo": 19}
