"""Pruebas de los casos de uso de trazabilidad (CU-14 a CU-16, Seccion
6.2) con un doble de RepositorioTrazabilidad -- sin Postgres real: las
consultas SQL y la verificacion de integridad en si se verifican aparte
(pruebas/prueba_repositorio_trazabilidad.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pytest

from app.dominio.puertos_comunes import Evento, Observabilidad
from app.dominio.trazabilidad.casos_uso import (
    ConsultarHistorialCuenta,
    ConsultarHistorialLote,
    ExportarExpediente,
    VisualizarIndicadoresCiclo,
)
from app.dominio.trazabilidad.errores import ErrorCuentaInexistente, ErrorLoteInexistente
from app.dominio.trazabilidad.valores import (
    DocumentoExpediente,
    EventoHistorial,
    FiltroIndicadores,
    HistorialCuenta,
    HistorialLote,
    IndicadoresCiclo,
    RegistrosContingencia,
    TiempoCicloCuentas,
)

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


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


def _observabilidad(registro_eventos: _RegistroEventosFalso) -> Observabilidad:
    return Observabilidad(eventos=registro_eventos, mediciones=_MedicionesFalso())


_EVENTO_REGISTRO = EventoHistorial(
    tipo_evento="REGISTRO",
    actor="ana.analista",
    estado_previo=None,
    estado_nuevo="REGISTRADA",
    ocurrido_en=_AHORA,
    datos={},
)


@dataclass
class _TrazabilidadFalso:
    existe: bool = True
    historial: HistorialCuenta = field(
        default_factory=lambda: HistorialCuenta(
            cuenta_medica_id=1, eventos=[_EVENTO_REGISTRO], cadena_integra=True
        )
    )
    documentos: list[DocumentoExpediente] = field(default_factory=list)
    indicadores: IndicadoresCiclo = field(
        default_factory=lambda: IndicadoresCiclo(
            tiempo_por_etapa=[],
            pct_lotes_observados=0.0,
            pct_lotes_rechazados=0.0,
            tasa_glosas=0.0,
            distribucion_por_estado=[],
            cartera_por_cobrar=Decimal("0.00"),
            lotes_evaluados=0,
            cuentas_evaluadas=0,
            lotes_por_periodo=[],
            por_iafas=[],
            tiempo_ciclo_cuentas=TiempoCicloCuentas(
                cuentas_cerradas=0,
                promedio_horas_cerradas=None,
                mediana_horas_cerradas=None,
                cuentas_abiertas=0,
                promedio_horas_abiertas=None,
                mas_antiguas_abiertas=[],
            ),
            registros_contingencia=RegistrosContingencia(total=0, pendientes_revision=0),
        )
    )
    ahora_recibido: datetime | None = None

    async def existe_cuenta(self, cuenta_medica_id: int) -> bool:
        return self.existe

    async def historial_de_cuenta(self, cuenta_medica_id: int) -> HistorialCuenta:
        return self.historial

    async def existe_lote(self, lote_id: int) -> bool:
        return self.existe

    async def historial_de_lote(self, lote_id: int) -> HistorialLote:
        return HistorialLote(
            lote_id=lote_id,
            eventos=[_EVENTO_REGISTRO],
            cadena_integra=self.historial.cadena_integra,
            rupturas=self.historial.rupturas,
        )

    async def documentos_de_cuenta(self, cuenta_medica_id: int) -> list[DocumentoExpediente]:
        return self.documentos

    async def calcular_indicadores(
        self, filtro: FiltroIndicadores, ahora: datetime | None = None
    ) -> IndicadoresCiclo:
        self.ahora_recibido = ahora
        return self.indicadores


# --- ConsultarHistorialLote (RT-13) ---------------------------------------


async def prueba_consultar_historial_de_lote_inexistente_es_rechazado() -> None:
    caso_uso = ConsultarHistorialLote(
        repositorio=_TrazabilidadFalso(existe=False),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
    )
    with pytest.raises(ErrorLoteInexistente):
        await caso_uso.ejecutar(7, actor="jefa.prueba")


async def prueba_consultar_historial_de_lote_registra_consulta_y_ruptura() -> None:
    registro_eventos = _RegistroEventosFalso()
    repositorio = _TrazabilidadFalso(
        historial=HistorialCuenta(
            cuenta_medica_id=1, eventos=[], cadena_integra=False, rupturas=["evento 3"]
        )
    )
    caso_uso = ConsultarHistorialLote(
        repositorio=repositorio, observabilidad=_observabilidad(registro_eventos)
    )
    historial = await caso_uso.ejecutar(7, actor="jefa.prueba")

    assert historial.lote_id == 7
    tipos = [e.tipo_evento for e in registro_eventos.eventos]
    assert tipos == ["HISTORIAL_CONSULTADO", "RUPTURA_CADENA_DETECTADA"]
    assert all(e.lote_id == 7 and e.cuenta_medica_id is None for e in registro_eventos.eventos)


# --- ConsultarHistorialCuenta (CU-14) -------------------------------------


async def prueba_consultar_historial_de_cuenta_inexistente_es_rechazado() -> None:
    caso_uso = ConsultarHistorialCuenta(
        repositorio=_TrazabilidadFalso(existe=False),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
    )
    with pytest.raises(ErrorCuentaInexistente):
        await caso_uso.ejecutar(1, actor="jefa.prueba")


async def prueba_consultar_historial_registra_la_consulta_en_la_bitacora() -> None:
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ConsultarHistorialCuenta(
        repositorio=_TrazabilidadFalso(),
        observabilidad=_observabilidad(registro_eventos),
    )
    historial = await caso_uso.ejecutar(1, actor="jefa.prueba")

    assert historial.cadena_integra is True
    assert len(registro_eventos.eventos) == 1
    assert registro_eventos.eventos[0].tipo_evento == "HISTORIAL_CONSULTADO"
    assert registro_eventos.eventos[0].cuenta_medica_id == 1
    assert registro_eventos.eventos[0].actor == "jefa.prueba"


async def prueba_consultar_historial_con_cadena_rota_emite_alerta() -> None:
    historial_roto = HistorialCuenta(
        cuenta_medica_id=1,
        eventos=[_EVENTO_REGISTRO],
        cadena_integra=False,
        rupturas=["version 2: el valor resumen no coincide"],
    )
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ConsultarHistorialCuenta(
        repositorio=_TrazabilidadFalso(historial=historial_roto),
        observabilidad=_observabilidad(registro_eventos),
    )
    historial = await caso_uso.ejecutar(1, actor="jefa.prueba")

    assert historial.cadena_integra is False
    tipos = [e.tipo_evento for e in registro_eventos.eventos]
    assert tipos == ["HISTORIAL_CONSULTADO", "RUPTURA_CADENA_DETECTADA"]
    assert registro_eventos.eventos[1].datos["rupturas"] == historial_roto.rupturas


# --- VisualizarIndicadoresCiclo (CU-15) -----------------------------------


async def prueba_visualizar_indicadores_delega_al_repositorio() -> None:
    repositorio = _TrazabilidadFalso()
    caso_uso = VisualizarIndicadoresCiclo(repositorio, _RelojFijo())
    resultado = await caso_uso.ejecutar(FiltroIndicadores(iafas_codigo="00012"))

    assert resultado is repositorio.indicadores
    # El tiempo de las cuentas abiertas se mide contra el reloj del caso
    # de uso, no contra el del sistema (pruebas reproducibles).
    assert repositorio.ahora_recibido == _RelojFijo().ahora()


# --- ExportarExpediente (CU-16) -------------------------------------------


async def prueba_exportar_expediente_de_cuenta_inexistente_es_rechazado() -> None:
    caso_uso = ExportarExpediente(
        repositorio=_TrazabilidadFalso(existe=False),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorCuentaInexistente):
        await caso_uso.ejecutar(1, "auditoria externa", actor="jefa.prueba")


async def prueba_exportar_expediente_registra_el_motivo_en_la_bitacora() -> None:
    documentos = [
        DocumentoExpediente(tipo="ACREDITACION", referencia="AUT-0001", emitido_en=_AHORA)
    ]
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ExportarExpediente(
        repositorio=_TrazabilidadFalso(documentos=documentos),
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    expediente = await caso_uso.ejecutar(1, "auditoria externa", actor="jefa.prueba")

    assert expediente.cuenta_medica_id == 1
    assert expediente.documentos == documentos
    assert expediente.generado_en == _AHORA
    assert registro_eventos.eventos[0].tipo_evento == "EXPEDIENTE_EXPORTADO"
    assert registro_eventos.eventos[0].datos["motivo"] == "auditoria externa"
