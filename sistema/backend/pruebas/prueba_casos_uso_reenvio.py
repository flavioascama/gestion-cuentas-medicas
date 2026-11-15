"""Pruebas de la correccion para el reenvio (T-05, Tabla 58, fila 11 de la
Tabla 66) con dobles de prueba: que solo una cuenta RECHAZADA puede
corregirse, que vuelve a FACTURADA por el motor y que el evento guarda
la descripcion de la correccion y el lote rechazado."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.dominio.orquestacion.casos_uso import CorregirCuentaRechazada, ObtenerRechazoCuenta
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.orquestacion.puertos import RechazoCuenta
from app.dominio.puertos_comunes import Evento, Observabilidad

_RECHAZO = RechazoCuenta(
    lote_id=7,
    numero_lote="0000007",
    motivo="estructura invalida",
    rechazado_en=datetime(2026, 9, 18, 10, 0, 0),
)


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _MedicionesFalso:
    async def registrar(self, medicion: object) -> None:
        pass


@dataclass
class _EstadoCuentaFalso:
    estados: dict[int, str]

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estados.get(cuenta_medica_id)

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        self.estados[cuenta_medica_id] = estado_nuevo


@dataclass
class _RechazosFalso:
    rechazo: RechazoCuenta | None

    async def obtener_ultimo_rechazo(self, cuenta_medica_id: int) -> RechazoCuenta | None:
        return self.rechazo


def _caso_uso(
    estado: str, rechazo: RechazoCuenta | None = _RECHAZO
) -> tuple[CorregirCuentaRechazada, _EstadoCuentaFalso, _RegistroEventosFalso]:
    estado_cuenta = _EstadoCuentaFalso(estados={1: estado})
    registro = _RegistroEventosFalso()
    caso_uso = CorregirCuentaRechazada(
        estado_cuenta=estado_cuenta,
        rechazos=_RechazosFalso(rechazo),
        observabilidad=Observabilidad(eventos=registro, mediciones=_MedicionesFalso()),
    )
    return caso_uso, estado_cuenta, registro


async def prueba_corregir_una_cuenta_rechazada_la_devuelve_a_facturada() -> None:
    caso_uso, estado_cuenta, registro = _caso_uso("RECHAZADA")

    estado_nuevo = await caso_uso.ejecutar(1, "se corrigio la serie del comprobante", "ana")

    assert estado_nuevo == "FACTURADA"
    assert estado_cuenta.estados[1] == "FACTURADA"
    (evento,) = registro.eventos
    assert evento.tipo_evento == "CORRECCION_REENVIO"
    assert (evento.estado_previo, evento.estado_nuevo) == ("RECHAZADA", "FACTURADA")
    assert evento.actor == "ana"
    assert evento.datos == {
        "descripcion_correccion": "se corrigio la serie del comprobante",
        "lote_rechazado_id": 7,
    }


@pytest.mark.parametrize("estado", ["FACTURADA", "ENVIADA", "EN_AUDITORIA", "CERRADA"])
async def prueba_corregir_rechaza_una_cuenta_que_no_esta_rechazada(estado: str) -> None:
    caso_uso, estado_cuenta, registro = _caso_uso(estado)

    with pytest.raises(ErrorTransicionNoDefinida):
        await caso_uso.ejecutar(1, "correccion", "ana")

    assert estado_cuenta.estados[1] == estado
    assert registro.eventos == []


async def prueba_obtener_rechazo_devuelve_el_del_repositorio() -> None:
    assert await ObtenerRechazoCuenta(_RechazosFalso(_RECHAZO)).ejecutar(1) == _RECHAZO
    assert await ObtenerRechazoCuenta(_RechazosFalso(None)).ejecutar(1) is None
