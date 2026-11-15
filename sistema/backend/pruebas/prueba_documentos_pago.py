"""Pruebas del comprobante de reemplazo (CU-10), de la nota de credito o
debito (RI-11) y su paso a la T1, y de los estados que el almacen admite
(Tabla 69)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.lote import NotaLote
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.orquestacion.motor import transicion_definida
from app.dominio.pse.documentos import (
    ComprobanteReemplazado,
    ComprobanteVigente,
    DatosNota,
    DocumentosPagoCuenta,
    EmisionPse,
    ErrorComprobanteConNota,
    ErrorEstadoNoAdmiteDocumento,
    ErrorNotaInvalida,
    ErrorNotaYaRegistrada,
    NotaDocumento,
    ReemplazarComprobantePago,
    RegistrarNotaDocumento,
)
from app.dominio.pse.puertos import ComprobantePse
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.tedef.constructor_lote import construir_t1, construir_t2
from app.infraestructura.tedef.escritor_ancho_fijo import escribir_registro
from pruebas.prueba_constructor_lote import _ESQUEMA, _contexto, _documento, _procedimiento

_AHORA = datetime(2026, 11, 13, 10, 0)
_VIGENTE = ComprobanteVigente(
    documento_id=4,
    tipo_documento_pago="01",
    serie="F001",
    numero="00000123",
    fecha_emision=date(2026, 9, 12),
)
_NOTA = DatosNota(
    tipo="C",
    serie="FC01",
    numero="45",
    monto=Decimal("80.00"),
    fecha=date(2026, 11, 10),
    motivo="D",
)


class _Reloj:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _EstadoFijo:
    estado: str | None = "GLOSADA"

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estado

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        raise AssertionError("no cambia el estado")


@dataclass
class _Documentos:
    nota: NotaDocumento | None = None
    reemplazos: list[tuple[ComprobantePse, ComprobanteReemplazado]] = field(default_factory=list)
    notas_guardadas: list[NotaDocumento] = field(default_factory=list)

    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        return DocumentosPagoCuenta(vigente=_VIGENTE, nota=self.nota)

    async def guardar_nota(self, documento_id: int, nota: NotaDocumento) -> None:
        self.notas_guardadas.append(nota)

    async def reemplazar(
        self, cuenta_medica_id: int, nuevo: ComprobantePse, reemplazo: ComprobanteReemplazado
    ) -> None:
        self.reemplazos.append((nuevo, reemplazo))


class _Comprobantes:
    async def obtener_ipress_propia(self) -> tuple[str, str]:
        return "20123456789", "00001234"

    async def guardar_comprobante(self, cuenta_id: int, comprobante: ComprobantePse) -> int:
        raise AssertionError("el reemplazo no crea otra fila")


class _Emisor:
    async def emitir(self, ruc_ipress: str, codigo_ipress: str) -> ComprobantePse:
        return ComprobantePse("01", "F001", "00000999", date(2026, 11, 13))


@dataclass
class _Registro:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


def _reemplazo(
    documentos: _Documentos, estado: str = "GLOSADA"
) -> tuple[ReemplazarComprobantePago, _Registro]:
    registro = _Registro()
    caso_uso = ReemplazarComprobantePago(
        documentos,
        EmisionPse(_Comprobantes(), _Emisor()),
        _EstadoFijo(estado),
        registro,
        _Reloj(),
    )
    return caso_uso, registro


async def prueba_reemplazo_emite_un_comprobante_nuevo_y_archiva_el_anterior() -> None:
    documentos = _Documentos()
    caso_uso, registro = _reemplazo(documentos)

    vigente = await caso_uso.ejecutar(7, "Refacturacion por glosa tecnica", "ana.analista")

    assert (vigente.documento_id, vigente.numero) == (4, "00000999")
    ((nuevo, archivado),) = documentos.reemplazos
    assert nuevo.numero == "00000999"
    assert (archivado.serie, archivado.numero) == ("F001", "00000123")
    assert archivado.motivo == "Refacturacion por glosa tecnica"
    (evento,) = registro.eventos
    assert evento.tipo_evento == "COMPROBANTE_PAGO_REEMPLAZADO"
    assert evento.datos["anterior"] == "F001-00000123"
    assert evento.datos["nuevo"] == "F001-00000999"


@pytest.mark.parametrize("estado", ["REGISTRADA", "FACTURADA", "EN_AUDITORIA", "CERRADA"])
async def prueba_reemplazo_solo_al_refacturar(estado: str) -> None:
    caso_uso, _ = _reemplazo(_Documentos(), estado)
    with pytest.raises(ErrorEstadoNoAdmiteDocumento):
        await caso_uso.ejecutar(7, "motivo", "ana.analista")


async def prueba_un_comprobante_con_nota_no_se_reemplaza() -> None:
    nota = NotaDocumento("C", "FC01", "00000045", Decimal("1"), date(2026, 11, 1), "D", _AHORA, "x")
    caso_uso, _ = _reemplazo(_Documentos(nota=nota))
    with pytest.raises(ErrorComprobanteConNota):
        await caso_uso.ejecutar(7, "motivo", "ana.analista")


async def prueba_registra_la_nota_con_el_numero_completo() -> None:
    documentos, registro = _Documentos(), _Registro()
    caso_uso = RegistrarNotaDocumento(
        documentos, _EstadoFijo("GLOSADA_PARCIAL"), registro, _Reloj()
    )

    nota = await caso_uso.ejecutar(7, _NOTA, "ana.analista")

    assert nota.numero == "00000045"
    assert documentos.notas_guardadas == [nota]
    (evento,) = registro.eventos
    assert evento.tipo_evento == "NOTA_DOCUMENTO_REGISTRADA"
    assert evento.datos["numero"] == "FC0100000045"


@pytest.mark.parametrize(
    "cambios",
    [
        {"tipo": "N"},
        {"motivo": "X"},
        {"serie": "F1"},
        {"numero": "123456789"},
        {"monto": Decimal("0")},
        {"fecha": date(2026, 9, 1)},
        {"fecha": date(2026, 11, 14)},
    ],
)
async def prueba_rechaza_una_nota_fuera_de_la_tabla_1(cambios: dict[str, Any]) -> None:
    caso_uso = RegistrarNotaDocumento(_Documentos(), _EstadoFijo(), _Registro(), _Reloj())
    with pytest.raises(ErrorNotaInvalida):
        await caso_uso.ejecutar(7, replace(_NOTA, **cambios), "ana.analista")


async def prueba_una_sola_nota_por_comprobante() -> None:
    nota = NotaDocumento("C", "FC01", "00000045", Decimal("1"), date(2026, 11, 1), "D", _AHORA, "x")
    caso_uso = RegistrarNotaDocumento(_Documentos(nota=nota), _EstadoFijo(), _Registro(), _Reloj())
    with pytest.raises(ErrorNotaYaRegistrada):
        await caso_uso.ejecutar(7, _NOTA, "ana.analista")


def _t1(nota: NotaLote | None) -> dict[int, str]:
    procedimiento = _procedimiento(1, "100.00")
    documento = replace(_documento((procedimiento,)), nota=nota)
    valores_t2 = construir_t2(_ESQUEMA["T2"], _contexto(), documento, (procedimiento,))
    valores_t1 = construir_t1(_ESQUEMA["T1"], _contexto(), documento, valores_t2)
    assert len(escribir_registro(_ESQUEMA["T1"], valores_t1)) == _ESQUEMA["T1"].longitud_registro
    return valores_t1


def prueba_t1_transmite_la_nota_del_comprobante() -> None:
    valores = _t1(NotaLote("C", "FC01", "00000045", Decimal("80.00"), date(2026, 11, 10), "D"))
    assert valores[25] == "C"
    assert valores[26] == "FC0100000045"
    assert valores[27].strip() == "80.00"
    assert valores[28] == "20261110"
    assert valores[29] == "D"


def prueba_t1_sin_nota_transmite_n_y_campos_en_blanco() -> None:
    valores = _t1(None)
    assert valores[25] == "N"
    assert all(valores[n].strip() == "" for n in (26, 27, 28, 29))


def prueba_transiciones_definidas_desde_el_almacen() -> None:
    assert transicion_definida("FACTURADA", "ENVIADA")
    assert transicion_definida("EN_AUDITORIA", "ANULADA")
    assert not transicion_definida("REGISTRADA", "EN_AUDITORIA")
    assert not transicion_definida("CERRADA", "ANULADA")


async def prueba_el_almacen_rechaza_estados_fuera_del_conjunto_o_de_la_tabla_58(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=88,
                tipo_evento="REGISTRO",
                actor="prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        with pytest.raises(ErrorTransicionNoDefinida):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=88,
                    tipo_evento="SALTO",
                    actor="prueba",
                    estado_previo="REGISTRADA",
                    estado_nuevo="EN_AUDITORIA",
                )
            )
        with pytest.raises(ErrorTransicionNoDefinida):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=None,
                    lote_id=5,
                    tipo_evento="LOTE_INVENTADO",
                    actor="prueba",
                    estado_previo=None,
                    estado_nuevo="PERDIDO",
                )
            )
