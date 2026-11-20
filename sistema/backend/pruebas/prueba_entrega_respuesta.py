"""Si la respuesta a una observacion de la aseguradora le llego
(2026-11-19): el estado de la entrega (pendiente, entregada, no entregada),
el pedido de una nueva entrega cuando la anterior agoto sus intentos y la
consulta SQL que junta la comunicacion con la cola."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.comunicaciones.casos_uso import (
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
)
from app.dominio.comunicaciones.entrega_respuesta import (
    ErrorEntregaDeOtro,
    ErrorEntregaNoDisponible,
    Solicitante,
    SolicitarNuevaEntregaRespuesta,
)
from app.dominio.observaciones.casos_uso import ListarObservacionesPorCuenta
from app.dominio.observaciones.entrega import EstadoEntrega, HechosEntrega, estado_entrega
from app.dominio.observaciones.valores import Naturaleza, Observacion
from app.infraestructura.persistencia.consulta_entregas_sql import ConsultaEntregasSql
from app.infraestructura.persistencia.modelos_comunicaciones import ComunicacionIafasModelo
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from pruebas.prueba_repositorio_observaciones import _sembrar_cuenta

_AHORA = datetime(2026, 11, 19, 10, 0, 0)


def _observacion(estado: str = "RESPONDIDA") -> Observacion:
    return Observacion(
        id=9,
        cuenta_medica_id=5,
        motivo_codigo="OBS-01",
        naturaleza=Naturaleza.ADMINISTRATIVA,
        es_parcial=False,
        detalle_campo_objetado=None,
        responsable_rol=NombreRol.ANALISTA,
        responsable_usuario_id=None,
        estado=estado,
        respuesta_texto="Se adjunta",
        respuesta_sustento="Informe",
        registrado_en=_AHORA,
        respondido_en=_AHORA,
    )


def _hechos(estado_trabajo: str | None, remitida: datetime | None = None) -> HechosEntrega:
    return HechosEntrega(
        remitida_en=remitida, estado_ultimo_trabajo=estado_trabajo, solicitada_por="aldo"
    )


def prueba_estado_de_la_entrega() -> None:
    respondida = _observacion()
    assert estado_entrega(respondida, None) is None  # no vino de la aseguradora
    assert estado_entrega(_observacion("ABIERTA"), _hechos("PENDIENTE")) is None
    assert estado_entrega(respondida, _hechos("PENDIENTE")) is EstadoEntrega.PENDIENTE
    assert estado_entrega(respondida, _hechos("EN_PROCESO")) is EstadoEntrega.PENDIENTE
    assert estado_entrega(respondida, _hechos("AGOTADO")) is EstadoEntrega.NO_ENTREGADA
    assert estado_entrega(respondida, _hechos(None)) is EstadoEntrega.NO_ENTREGADA
    entregada = _hechos("COMPLETADO", _AHORA)
    assert estado_entrega(respondida, entregada) is EstadoEntrega.ENTREGADA


@dataclass
class _Observaciones:
    observacion: Observacion

    async def obtener(self, observacion_id: int) -> Observacion | None:
        return self.observacion if observacion_id == self.observacion.id else None

    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[Observacion]:
        return [self.observacion]


@dataclass
class _Entregas:
    por_observacion: dict[int, HechosEntrega]

    async def hechos(self, cuenta_medica_id: int) -> dict[int, HechosEntrega]:
        return self.por_observacion


@dataclass
class _Encolar:
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)

    async def ejecutar(self, *argumentos: Any) -> int | None:
        self.llamadas.append(argumentos)
        return 31


def _caso(hechos: HechosEntrega | None, encolar: _Encolar) -> SolicitarNuevaEntregaRespuesta:
    entregas = _Entregas({} if hechos is None else {9: hechos})
    return SolicitarNuevaEntregaRespuesta(
        _Observaciones(_observacion()),  # type: ignore[arg-type]
        entregas,
        encolar,  # type: ignore[arg-type]
    )


async def prueba_quien_respondio_vuelve_a_pedir_la_entrega_agotada() -> None:
    encolar = _Encolar()
    trabajo = await _caso(_hechos("AGOTADO"), encolar).ejecutar(
        9, Solicitante("aldo", frozenset({NombreRol.AUDITOR}))
    )

    assert trabajo == 31
    assert encolar.llamadas == [(9, "Se adjunta", "Informe", "aldo")]


async def prueba_el_analista_tambien_puede_pedirla() -> None:
    encolar = _Encolar()
    await _caso(_hechos("AGOTADO"), encolar).ejecutar(
        9, Solicitante("ana", frozenset({NombreRol.ANALISTA}))
    )
    assert len(encolar.llamadas) == 1


async def prueba_otra_persona_no_la_pide() -> None:
    with pytest.raises(ErrorEntregaDeOtro):
        await _caso(_hechos("AGOTADO"), _Encolar()).ejecutar(
            9, Solicitante("otro", frozenset({NombreRol.AUDITOR}))
        )


@pytest.mark.parametrize("hechos", [None, _hechos("PENDIENTE"), _hechos("COMPLETADO", _AHORA)])
async def prueba_no_se_pide_si_no_vino_de_la_iafas_esta_en_curso_o_ya_llego(
    hechos: HechosEntrega | None,
) -> None:
    encolar = _Encolar()
    with pytest.raises(ErrorEntregaNoDisponible):
        await _caso(hechos, encolar).ejecutar(
            9, Solicitante("ana", frozenset({NombreRol.ANALISTA}))
        )
    assert encolar.llamadas == []


async def prueba_la_lista_de_la_cuenta_muestra_la_entrega() -> None:
    caso = ListarObservacionesPorCuenta(
        _Observaciones(_observacion()),  # type: ignore[arg-type]
        _Entregas({9: _hechos("COMPLETADO", _AHORA)}),
    )
    (observacion,) = await caso.ejecutar(5)

    assert observacion.entrega_estado == "ENTREGADA"
    assert observacion.entrega_en == _AHORA
    assert observacion.entrega_solicitada_por == "aldo"


def _comunicacion(cuenta_id: int, observacion_id: int, remitida: datetime | None) -> Any:
    return ComunicacionIafasModelo(
        codigo=f"COM-{observacion_id:08d}",
        canal="PORTAL",
        tipo="OBSERVACION",
        codigo_iafas="20001",
        codigo_ipress="15995250",
        documento="F00100000123",
        datos={},
        emitida_en="2026-11-19T08:00:00",
        cuenta_medica_id=cuenta_id,
        resultado="APLICADA",
        observacion_id=observacion_id,
        recibida_en=_AHORA,
        respuesta_remitida_en=remitida,
    )


def _trabajo(cuenta_id: int, observacion_id: int, estado: str, quien: str) -> TrabajoModelo:
    return TrabajoModelo(
        tipo=TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
        carga_util={
            "cuenta_medica_id": cuenta_id,
            "observacion_id": observacion_id,
            "usuario_origen": quien,
        },
        estado=estado,
        intentos=0,
        proximo_intento=_AHORA,
    )


async def prueba_consulta_sql_junta_comunicacion_y_cola(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        sesion.add_all(
            [
                _comunicacion(cuenta_id, 1, None),
                _comunicacion(cuenta_id, 2, _AHORA),
                _trabajo(cuenta_id, 1, "AGOTADO", "aldo"),
                _trabajo(cuenta_id, 1, "PENDIENTE", "ana"),
                _trabajo(cuenta_id, 2, "COMPLETADO", "aldo"),
            ]
        )
        await sesion.flush()
        hechos = await ConsultaEntregasSql(sesion).hechos(cuenta_id)

    assert hechos[1] == HechosEntrega(None, "PENDIENTE", "aldo")
    assert hechos[2].estado_ultimo_trabajo == "COMPLETADO"
    assert hechos[2].remitida_en is not None
    assert set(hechos) == {1, 2}
