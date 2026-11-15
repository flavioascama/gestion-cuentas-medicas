"""Pruebas del caso de uso RemitirLote (Seccion 7.8, precondicion ajustada
en la Fase 13) con un repositorio y un transmisor falsos: verifican la
maquina de estados (que solo remite un lote VALIDADO, que un fallo de
transferencia no cambia nada) sin tocar Postgres ni una red real -- eso se
verifica aparte, contra el simulador real en Docker (ver
docs/DECISIONES.md, Fase 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from app.compartido.huella import huella_sha256
from app.dominio.integracion.puertos import (
    ErrorLoteNoRemisible,
    LoteParaRemitir,
    ResultadoTransmision,
)
from app.dominio.puertos_comunes import Evento, MedicionPaso, Observabilidad
from app.infraestructura.tedef.remitir_lote import RemitirLote

_CONTENIDO = b"contenido de prueba del .S01"
_HUELLA = huella_sha256(_CONTENIDO)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RepositorioFalso:
    lote: LoteParaRemitir | None
    remisiones_registradas: list[dict[str, object]] = field(default_factory=list)

    async def obtener_lote_para_remision(self, lote_id: int) -> LoteParaRemitir | None:
        return self.lote

    async def registrar_remision(
        self,
        lote_id: int,
        documento_ids: tuple[int, ...],
        exitosa: bool,
        motivo: str | None,
        instante: datetime,
    ) -> tuple[int, tuple[int, ...]]:
        self.remisiones_registradas.append(
            {
                "lote_id": lote_id,
                "documento_ids": documento_ids,
                "exitosa": exitosa,
                "motivo": motivo,
                "instante": instante,
            }
        )
        return len(self.remisiones_registradas), ((20, 21) if exitosa else ())


@dataclass
class _TransmisorFalso:
    resultado: ResultadoTransmision
    llamadas: list[tuple[str, bytes]] = field(default_factory=list)

    async def transmitir(self, nombre_archivo: str, contenido: bytes) -> ResultadoTransmision:
        self.llamadas.append((nombre_archivo, contenido))
        return self.resultado


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


@dataclass
class _RepositorioTrabajosFalso:
    trabajos_encolados: list[dict[str, object]] = field(default_factory=list)

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.trabajos_encolados.append(
            {"tipo": tipo, "carga_util": carga_util, "proximo_intento": proximo_intento}
        )
        return len(self.trabajos_encolados)


_NOMBRE_S01 = "937_20100121809_00140456_20002_0000001_202609_20260916.S01"


def _lote(tmp_path: Path, estado: str = "VALIDADO") -> LoteParaRemitir:
    return LoteParaRemitir(
        lote_id=1,
        numero="0000001",
        estado=estado,
        nombre_s01=_NOMBRE_S01,
        sha256_s01=_HUELLA,
        ruta_s01=str(tmp_path / _NOMBRE_S01),
        documento_ids=(10, 11),
    )


def _construir(
    lote: LoteParaRemitir | None, resultado_transmision: ResultadoTransmision
) -> tuple[
    RemitirLote,
    _RepositorioFalso,
    _TransmisorFalso,
    _RegistroEventosFalso,
    _RepositorioTrabajosFalso,
]:
    if lote is not None and lote.ruta_s01 is not None:
        Path(lote.ruta_s01).write_bytes(_CONTENIDO)
    repositorio = _RepositorioFalso(lote=lote)
    transmisor = _TransmisorFalso(resultado=resultado_transmision)
    registro_eventos = _RegistroEventosFalso()
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = RemitirLote(
        repositorio=repositorio,  # type: ignore[arg-type]
        transmisor=transmisor,  # type: ignore[arg-type]
        observabilidad=Observabilidad(
            eventos=registro_eventos,  # type: ignore[arg-type]
            mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        ),
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )
    return caso_uso, repositorio, transmisor, registro_eventos, repositorio_trabajos


async def prueba_remite_un_lote_validado_con_exito(tmp_path: Path) -> None:
    lote = _lote(tmp_path)
    caso_uso, repositorio, transmisor, registro_eventos, _ = _construir(
        lote, ResultadoTransmision(exitosa=True)
    )
    resultado = await caso_uso.ejecutar(lote_id=1, actor="prueba")

    assert resultado.exitosa
    assert transmisor.llamadas == [(_NOMBRE_S01, _CONTENIDO)]
    assert repositorio.remisiones_registradas[0]["exitosa"] is True
    assert registro_eventos.eventos[0].tipo_evento == "LOTE_REMITIDO"


async def prueba_remision_exitosa_registra_un_evento_por_cuenta(tmp_path: Path) -> None:
    """T-03 (Seccion 5.2.4, RF-16/RT-01): ademas del evento del lote, cada
    cuenta que paso a ENVIADA deja su propio evento, para que su historial
    muestre el envio y el panel pueda medir la etapa."""

    caso_uso, _, _, registro_eventos, _ = _construir(
        _lote(tmp_path), ResultadoTransmision(exitosa=True)
    )
    await caso_uso.ejecutar(lote_id=1, actor="ana.analista")

    eventos_cuenta = registro_eventos.eventos[1:]
    assert [e.tipo_evento for e in eventos_cuenta] == ["CUENTA_ENVIADA"] * 2
    assert [e.cuenta_medica_id for e in eventos_cuenta] == [20, 21]
    assert all(e.estado_previo == "FACTURADA" for e in eventos_cuenta)
    assert all(e.estado_nuevo == "ENVIADA" for e in eventos_cuenta)
    assert all(e.datos["lote_id"] == 1 for e in eventos_cuenta)


async def prueba_remision_exitosa_encola_monitoreo_de_respuesta(tmp_path: Path) -> None:
    caso_uso, _, _, _, repositorio_trabajos = _construir(
        _lote(tmp_path), ResultadoTransmision(exitosa=True)
    )
    await caso_uso.ejecutar(lote_id=1, actor="prueba")

    assert len(repositorio_trabajos.trabajos_encolados) == 1
    trabajo = repositorio_trabajos.trabajos_encolados[0]
    assert trabajo["tipo"] == "MONITOREAR_RESPUESTA_IAFAS"
    assert trabajo["carga_util"] == {"lote_id": 1, "usuario_origen": "prueba"}


async def prueba_no_remite_un_lote_generado_sin_validar(tmp_path: Path) -> None:
    caso_uso, _, transmisor, _, _ = _construir(
        _lote(tmp_path, estado="GENERADO"), ResultadoTransmision(exitosa=True)
    )
    with pytest.raises(ErrorLoteNoRemisible):
        await caso_uso.ejecutar(lote_id=1, actor="prueba")
    assert transmisor.llamadas == []


async def prueba_no_remite_un_lote_ya_remitido(tmp_path: Path) -> None:
    caso_uso, _, transmisor, _, _ = _construir(
        _lote(tmp_path, estado="REMITIDO_IAFAS"), ResultadoTransmision(exitosa=True)
    )
    with pytest.raises(ErrorLoteNoRemisible):
        await caso_uso.ejecutar(lote_id=1, actor="prueba")
    assert transmisor.llamadas == []


async def prueba_no_remite_un_lote_inexistente() -> None:
    caso_uso, _, transmisor, _, _ = _construir(None, ResultadoTransmision(exitosa=True))
    with pytest.raises(ErrorLoteNoRemisible):
        await caso_uso.ejecutar(lote_id=1, actor="prueba")
    assert transmisor.llamadas == []


async def prueba_registra_un_fallo_de_transferencia_sin_marcar_remitido(tmp_path: Path) -> None:
    caso_uso, repositorio, transmisor, registro_eventos, repositorio_trabajos = _construir(
        _lote(tmp_path), ResultadoTransmision(exitosa=False, motivo="conexion rechazada")
    )
    resultado = await caso_uso.ejecutar(lote_id=1, actor="prueba")

    assert not resultado.exitosa
    assert resultado.motivo == "conexion rechazada"
    assert repositorio.remisiones_registradas[0]["exitosa"] is False
    assert registro_eventos.eventos[0].tipo_evento == "LOTE_REMISION_FALLIDA"
    assert repositorio_trabajos.trabajos_encolados == []


async def prueba_rechaza_un_archivo_cuya_huella_no_coincide(tmp_path: Path) -> None:
    lote = _lote(tmp_path)
    assert lote.ruta_s01 is not None
    Path(lote.ruta_s01).write_bytes(b"contenido distinto al validado")
    repositorio = _RepositorioFalso(lote=lote)
    transmisor = _TransmisorFalso(resultado=ResultadoTransmision(exitosa=True))
    caso_uso = RemitirLote(
        repositorio=repositorio,  # type: ignore[arg-type]
        transmisor=transmisor,  # type: ignore[arg-type]
        observabilidad=Observabilidad(
            eventos=_RegistroEventosFalso(),  # type: ignore[arg-type]
            mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        ),
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )
    with pytest.raises(ErrorLoteNoRemisible):
        await caso_uso.ejecutar(lote_id=1, actor="prueba")
    assert transmisor.llamadas == []
