"""Pruebas unitarias de EmitirComprobantePago (adenda de ingesta y
completitud, emision via el simulador PSE), con repositorios falsos en
memoria (Seccion 12.1: no dependen de una base de datos)."""

from __future__ import annotations

from datetime import date

from app.dominio.pse.casos_uso import EmitirComprobantePago
from app.dominio.pse.puertos import (
    ComprobantePse,
    EmisorPse,
    RepositorioComprobantePago,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos

_COMPROBANTE = ComprobantePse(
    tipo_documento_pago="01", serie="F001", numero="00000007", fecha_emision=date(2026, 9, 28)
)


class EmisorPseFalso(EmisorPse):
    def __init__(self, comprobante: ComprobantePse = _COMPROBANTE) -> None:
        self._comprobante = comprobante
        self.llamadas: list[tuple[str, str]] = []

    async def emitir(self, ruc_ipress: str, codigo_ipress: str) -> ComprobantePse:
        self.llamadas.append((ruc_ipress, codigo_ipress))
        return self._comprobante


class RepositorioComprobanteFalso(RepositorioComprobantePago):
    def __init__(self) -> None:
        self.guardado: tuple[int, ComprobantePse] | None = None

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        return "20123456789", "15995250"

    async def guardar_comprobante(self, cuenta_id: int, comprobante: ComprobantePse) -> int:
        self.guardado = (cuenta_id, comprobante)
        return 42


class RegistroEventosFalso(RegistroEventos):
    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


async def prueba_emitir_comprobante_pago_usa_la_ipress_propia_y_persiste() -> None:
    repositorio = RepositorioComprobanteFalso()
    emisor = EmisorPseFalso()
    eventos = RegistroEventosFalso()
    caso_uso = EmitirComprobantePago(repositorio, emisor, eventos)

    resultado = await caso_uso.ejecutar(79, "ana.analista")

    assert resultado.documento_id == 42
    assert resultado.comprobante == _COMPROBANTE
    assert emisor.llamadas == [("20123456789", "15995250")]
    assert repositorio.guardado == (79, _COMPROBANTE)


async def prueba_emitir_comprobante_pago_registra_evento() -> None:
    repositorio = RepositorioComprobanteFalso()
    emisor = EmisorPseFalso()
    eventos = RegistroEventosFalso()
    caso_uso = EmitirComprobantePago(repositorio, emisor, eventos)

    await caso_uso.ejecutar(79, "ana.analista")

    assert len(eventos.eventos) == 1
    evento = eventos.eventos[0]
    assert evento.tipo_evento == "COMPROBANTE_PAGO_EMITIDO"
    assert evento.cuenta_medica_id == 79
    assert evento.actor == "ana.analista"
    assert evento.datos["serie"] == "F001"
    assert evento.datos["numero"] == "00000007"
