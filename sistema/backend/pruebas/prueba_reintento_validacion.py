"""Nueva solicitud de la validacion de un lote CARGADO_VALIDADOR cuyo
trabajo agoto sus reintentos (la tesis habla de "la ultima solicitud")."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.casos_uso_validacion import (
    TIPO_EVENTO_VALIDACION_SOLICITADA,
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
    SolicitarCargaEnValidador,
)
from app.dominio.integracion.puertos_validacion import ErrorLoteNoCargable
from app.infraestructura.persistencia.modelos_integracion import (
    LoteFacturacionModelo,
    TrabajoModelo,
)
from app.infraestructura.persistencia.repositorio_lotes_consulta_sql import (
    RepositorioLotesConsultaSql,
)
from pruebas import prueba_casos_uso_validacion_tedef as validacion
from pruebas.prueba_lotes_sugeridos import _crear_cuenta
from pruebas.prueba_vigencia_lote_sql import _base, _lote


@dataclass
class _Trabajos(validacion._RepositorioTrabajosFalso):
    en_curso: bool = False
    consultas: list[tuple[str, int]] = field(default_factory=list)

    async def hay_sin_terminar(self, tipo: str, lote_id: int) -> bool:
        self.consultas.append((tipo, lote_id))
        return self.en_curso


def _caso(estado: str, trabajos: _Trabajos) -> tuple[SolicitarCargaEnValidador, list]:
    observabilidad, eventos, _ = validacion._observabilidad()
    caso_uso = SolicitarCargaEnValidador(
        validacion._RepositorioValidacionFalso(estado_lote=estado),  # type: ignore[arg-type]
        trabajos,  # type: ignore[arg-type]
        validacion._RelojFijo(validacion._INSTANTE),
        observabilidad,
    )
    return caso_uso, eventos.eventos


async def prueba_un_lote_cargado_sin_trabajo_en_curso_se_vuelve_a_validar() -> None:
    trabajos = _Trabajos()
    caso_uso, eventos = _caso("CARGADO_VALIDADOR", trabajos)

    trabajo_id = await caso_uso.ejecutar(lote_id=4, actor="jefe.cuentas")

    assert trabajos.consultas == [(TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR, 4)]
    assert trabajos.encolados[0]["tipo"] == TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR
    (evento,) = eventos
    assert (evento.tipo_evento, evento.lote_id, evento.actor) == (
        TIPO_EVENTO_VALIDACION_SOLICITADA,
        4,
        "jefe.cuentas",
    )
    assert evento.datos == {"lote_id": 4, "trabajo_id": trabajo_id}


async def prueba_no_se_duplica_una_validacion_en_curso() -> None:
    trabajos = _Trabajos(en_curso=True)
    caso_uso, eventos = _caso("CARGADO_VALIDADOR", trabajos)

    with pytest.raises(ErrorLoteNoCargable, match="en curso"):
        await caso_uso.ejecutar(lote_id=4, actor="ana")
    assert trabajos.encolados == [] and eventos == []


async def prueba_la_primera_carga_no_deja_evento_de_nueva_solicitud() -> None:
    trabajos = _Trabajos()
    caso_uso, eventos = _caso("GENERADO", trabajos)

    await caso_uso.ejecutar(lote_id=4, actor="ana")

    assert len(trabajos.encolados) == 1 and eventos == [] and trabajos.consultas == []


def _trabajo(lote_id: int, estado: str) -> TrabajoModelo:
    instante = datetime(2026, 11, 19, 9, 0, 0, tzinfo=UTC)
    return TrabajoModelo(
        tipo=TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
        carga_util={"lote_id": lote_id},
        estado=estado,
        intentos=5,
        proximo_intento=instante,
        creado_en=instante,
        actualizado_en=instante,
    )


async def prueba_el_detalle_dice_si_la_validacion_se_puede_volver_a_pedir(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        documento = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        lote_id = await _lote(sesion, iafas, [documento], estado="CARGADO_VALIDADOR")
        sesion.add(_trabajo(lote_id, "AGOTADO"))
        await sesion.flush()
        repositorio = RepositorioLotesConsultaSql(sesion)

        detalle = await repositorio.obtener(lote_id)
        assert detalle is not None and detalle.validacion_reintentable

        sesion.add(_trabajo(lote_id, "PENDIENTE"))
        await sesion.flush()
        detalle = await repositorio.obtener(lote_id)
        assert detalle is not None and not detalle.validacion_reintentable

        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        assert lote is not None
        lote.estado = "GENERADO"
        await sesion.flush()
        detalle = await repositorio.obtener(lote_id)
        assert detalle is not None and not detalle.validacion_reintentable
