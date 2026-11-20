"""Pruebas unitarias de EmitirComprobantePago (adenda de ingesta y
completitud, emision via el simulador PSE), con repositorios falsos en
memoria (Seccion 12.1: no dependen de una base de datos)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.dominio.pse.casos_uso import EmitirComprobantePago
from app.dominio.pse.puertos import (
    ClienteComprobante,
    ComprobanteEmitido,
    ComprobantePse,
    DatosFacturacion,
    EmisorPse,
    ErrorFaltaParaFacturar,
    MontosComprobante,
    NotaPse,
    RepositorioComprobantePago,
    RequisitosComprobante,
    SolicitudComprobante,
    SolicitudNota,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos

_COMPROBANTE = ComprobantePse(
    tipo_documento_pago="01", serie="F001", numero="00000007", fecha_emision=date(2026, 9, 28)
)
_MONTOS = MontosComprobante(
    valor_venta=Decimal("60.00"), igv=Decimal("10.80"), total=Decimal("70.80")
)
_CLIENTE = ClienteComprobante(codigo_iafas="19395", razon_social="IAFAS de prueba")


class EmisorPseFalso(EmisorPse):
    def __init__(self, comprobante: ComprobantePse = _COMPROBANTE) -> None:
        self._comprobante = comprobante
        self.llamadas: list[SolicitudComprobante] = []

    async def emitir_nota(self, solicitud: SolicitudNota) -> NotaPse:
        raise AssertionError("estas pruebas no emiten notas")

    async def emitir(self, solicitud: SolicitudComprobante) -> ComprobantePse:
        self.llamadas.append(solicitud)
        return self._comprobante


class RepositorioComprobanteFalso(RepositorioComprobantePago):
    def __init__(self) -> None:
        self.guardado: tuple[int, ComprobanteEmitido] | None = None
        self.requisitos: RequisitosComprobante | None = RequisitosComprobante(
            acreditada=True, con_diagnostico=True, procedimientos=1
        )

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        return "20123456789", "15995250"

    async def requisitos_para_facturar(self, cuenta_id: int) -> RequisitosComprobante | None:
        return self.requisitos

    async def datos_para_facturar(
        self, cuenta_id: int, tipo_comprobante: str
    ) -> DatosFacturacion | None:
        return DatosFacturacion(cliente=_CLIENTE, montos=_MONTOS)

    async def guardar_comprobante(self, cuenta_id: int, emitido: ComprobanteEmitido) -> int:
        self.guardado = (cuenta_id, emitido)
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
    # El PSE recibe la factura, la IAFAS como cliente y los montos ya calculados.
    assert emisor.llamadas == [
        SolicitudComprobante("20123456789", "15995250", "01", _CLIENTE, _MONTOS)
    ]
    # Y se guarda exactamente lo enviado.
    assert repositorio.guardado == (79, ComprobanteEmitido(_COMPROBANTE, _MONTOS))


async def prueba_no_se_emite_un_comprobante_sin_nada_que_facturar() -> None:
    repositorio = RepositorioComprobanteFalso()
    repositorio.requisitos = RequisitosComprobante(
        acreditada=True, con_diagnostico=False, procedimientos=0
    )
    emisor = EmisorPseFalso()
    caso_uso = EmitirComprobantePago(repositorio, emisor, RegistroEventosFalso())

    with pytest.raises(ErrorFaltaParaFacturar) as error:
        await caso_uso.ejecutar(79, "ana.analista")

    assert error.value.faltantes == ("el diagnóstico principal", "al menos un procedimiento")
    # No se le pide un numero al PSE ni se guarda nada.
    assert emisor.llamadas == [] and repositorio.guardado is None


async def prueba_no_se_emite_un_comprobante_a_un_asegurado_no_acreditable() -> None:
    repositorio = RepositorioComprobanteFalso()
    repositorio.requisitos = RequisitosComprobante(
        acreditada=True, con_diagnostico=True, procedimientos=1, acreditable=False
    )
    emisor = EmisorPseFalso()
    caso_uso = EmitirComprobantePago(repositorio, emisor, RegistroEventosFalso())

    with pytest.raises(ErrorFaltaParaFacturar) as error:
        await caso_uso.ejecutar(79, "ana.analista")

    assert error.value.faltantes == ("que la aseguradora acredite al asegurado",)
    assert emisor.llamadas == [] and repositorio.guardado is None


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
