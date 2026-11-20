"""Copago a la vista y su cobro registrado (2026-11-19): el registro
manual (una vez por cuenta, nunca en una cuenta cerrada o anulada) y el
copago que el calculo de montos atribuye al asegurado."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.integracion.copago_cobrado import (
    CopagoCobrado,
    DatosCobroCopago,
    ErrorCopagoInvalido,
    ErrorCopagoYaRegistrado,
    ErrorCuentaCerradaCopago,
    ErrorCuentaInexistenteCopago,
    RegistrarCopagoCobrado,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import AcreditacionModelo
from pruebas.prueba_rutas_atenciones_hospitalarias import Token, _cabeceras, _importar, _sembrar

_AHORA = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
_COBRO = DatosCobroCopago(monto=Decimal("20.00"), fecha=date(2026, 11, 19), referencia=" CJ-001 ")


class _Copagos:
    def __init__(self) -> None:
        self.filas: dict[int, CopagoCobrado] = {}

    async def obtener(self, cuenta_medica_id: int) -> CopagoCobrado | None:
        return self.filas.get(cuenta_medica_id)

    async def registrar(self, cuenta_medica_id: int, copago: CopagoCobrado) -> int:
        self.filas[cuenta_medica_id] = copago
        return 1


class _Estado:
    def __init__(self, estado: str | None) -> None:
        self._estado = estado

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self._estado


class _Eventos:
    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _Reloj:
    def ahora(self) -> datetime:
        return _AHORA


def _caso_uso(
    estado: str | None = "FACTURADA",
) -> tuple[RegistrarCopagoCobrado, _Copagos, _Eventos]:
    copagos, eventos = _Copagos(), _Eventos()
    caso_uso = RegistrarCopagoCobrado(copagos, _Estado(estado), eventos, _Reloj())  # type: ignore[arg-type]
    return caso_uso, copagos, eventos


async def prueba_registra_el_cobro_manual_con_su_evento() -> None:
    caso_uso, copagos, eventos = _caso_uso()

    copago = await caso_uso.ejecutar(5, _COBRO, "ana.analista")

    assert copagos.filas[5] == copago
    assert (copago.referencia, copago.origen, copago.registrado_por) == (
        "CJ-001",
        "manual",
        "ana.analista",
    )
    (evento,) = eventos.eventos
    assert (evento.tipo_evento, evento.actor, evento.cuenta_medica_id) == (
        "COPAGO_COBRADO_REGISTRADO",
        "ana.analista",
        5,
    )
    assert evento.datos == {"monto": "20.00", "origen": "manual"}


async def prueba_no_registra_un_segundo_cobro() -> None:
    caso_uso, _, eventos = _caso_uso()
    await caso_uso.ejecutar(5, _COBRO, "ana.analista")

    with pytest.raises(ErrorCopagoYaRegistrado):
        await caso_uso.ejecutar(5, _COBRO, "ana.analista")

    assert len(eventos.eventos) == 1


@pytest.mark.parametrize("estado", ["CERRADA", "ANULADA"])
async def prueba_no_registra_el_cobro_en_una_cuenta_terminal(estado: str) -> None:
    caso_uso, copagos, eventos = _caso_uso(estado)

    with pytest.raises(ErrorCuentaCerradaCopago):
        await caso_uso.ejecutar(5, _COBRO, "ana.analista")

    assert copagos.filas == {} and eventos.eventos == []


async def prueba_no_registra_el_cobro_de_una_cuenta_inexistente() -> None:
    caso_uso, _, _ = _caso_uso(None)

    with pytest.raises(ErrorCuentaInexistenteCopago):
        await caso_uso.ejecutar(5, _COBRO, "ana.analista")


@pytest.mark.parametrize(
    "monto,fecha,referencia",
    [
        ("0", date(2026, 11, 19), "CJ-1"),
        ("-5.00", date(2026, 11, 19), "CJ-1"),
        ("20.00", date(2026, 11, 20), "CJ-1"),
        ("20.00", date(2026, 11, 19), "   "),
        ("20.00", date(2026, 11, 19), "X" * 61),
    ],
)
async def prueba_valida_monto_fecha_y_referencia(monto: str, fecha: date, referencia: str) -> None:
    caso_uso, copagos, _ = _caso_uso()

    with pytest.raises(ErrorCopagoInvalido):
        await caso_uso.ejecutar(5, DatosCobroCopago(Decimal(monto), fecha, referencia), "a")

    assert copagos.filas == {}


@pytest.fixture
async def base(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar(sesion)


async def prueba_el_analista_registra_el_cobro_por_la_ruta_una_sola_vez(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    cuenta_id = (await _importar(cliente, analista, copago_cobrado=None)).json()["cuenta_id"]
    ruta = f"/cuentas/{cuenta_id}/copago-cobrado"
    cuerpo = {"monto": "15.50", "fecha": "2026-11-18", "referencia": "CJ-0099"}

    sin_cobro = await cliente.get(ruta, headers=analista)
    primero = await cliente.post(ruta, json=cuerpo, headers=analista)
    segundo = await cliente.post(ruta, json=cuerpo, headers=analista)
    leido = (await cliente.get(ruta, headers=analista)).json()

    assert sin_cobro.json() is None
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 409
    assert segundo.json()["codigo"] == "COPAGO_YA_REGISTRADO"
    assert (leido["monto"], leido["referencia"], leido["origen"]) == ("15.50", "CJ-0099", "manual")


async def prueba_la_ruta_rechaza_un_cobro_invalido_o_ya_traido_de_la_atencion(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]
    ruta = f"/cuentas/{cuenta_id}/copago-cobrado"

    futuro = await cliente.post(
        ruta, json={"monto": "5.00", "fecha": "2999-01-01", "referencia": "CJ"}, headers=analista
    )
    repetido = await cliente.post(
        ruta, json={"monto": "5.00", "fecha": "2026-11-18", "referencia": "CJ"}, headers=analista
    )

    assert (futuro.status_code, futuro.json()["codigo"]) == (422, "COPAGO_INVALIDO")
    assert repetido.status_code == 409


async def prueba_copago_del_asegurado_segun_el_calculo_de_montos(
    base: None,
    cliente: AsyncClient,
    token_para_rol: Token,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    tesoreria = await _cabeceras(token_para_rol, NombreRol.TESORERIA)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]
    ruta = f"/cuentas/{cuenta_id}/copago-asegurado"
    sin_acreditacion = (await cliente.get(ruta, headers=analista)).json()
    async with fabrica_sesiones() as sesion:
        sesion.add(
            AcreditacionModelo(
                cuenta_id=cuenta_id,
                condicion_cobertura="ACREDITABLE",
                codigo_autorizacion="AUT1",
                tipo_documento_autorizacion="01",
                codigo_asegurado="AS1",
                tipo_afiliacion="1",
                instante=datetime.now(UTC),
                componente_ejecutor="prueba",
                tipo_copago="coaseguro",
                porcentaje_coaseguro=20,
            )
        )
        await sesion.commit()

    con_acreditacion = await cliente.get(ruta, headers=tesoreria)

    assert sin_acreditacion == {"monto": None}
    # La farmacia de la atencion: 2 x 12.50 con 20 % de coaseguro.
    assert con_acreditacion.json() == {"monto": "5.00"}
