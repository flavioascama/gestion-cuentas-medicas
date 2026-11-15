"""Pruebas de la carta de garantia (RF-13, CU-06): validaciones del caso de
uso y su uso en el aviso de vigencia (hito 5 de la Tabla 61)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acreditacion.carta_garantia import (
    CartaGarantia,
    DatosCartaGarantia,
    ErrorCartaGarantiaInvalida,
    ErrorCartaGarantiaYaRegistrada,
    ErrorCuentaInexistenteCarta,
    ErrorCuentaSinRegistroCarta,
    RegistrarCartaGarantia,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.repositorio_carta_garantia_sql import (
    RepositorioCartaGarantiaSql,
)
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql
from pruebas.prueba_repositorio_plazos import _AHORA, _sembrar_cuenta, _sembrar_iafas

_DATOS = DatosCartaGarantia(
    numero="CG-2026-0001",
    vigente_desde=date(2026, 11, 1),
    vigente_hasta=date(2026, 11, 30),
    monto=Decimal("1500.00"),
)


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _EstadoFijo:
    estado: str | None

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estado

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        raise AssertionError("registrar la carta no cambia el estado de la cuenta")


@dataclass
class _RepositorioFalso:
    cartas: dict[int, CartaGarantia] = field(default_factory=dict)

    async def obtener(self, cuenta_medica_id: int) -> CartaGarantia | None:
        return self.cartas.get(cuenta_medica_id)

    async def guardar(self, carta: CartaGarantia) -> None:
        self.cartas[carta.cuenta_medica_id] = carta


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


def _caso_uso(
    estado: str | None = "REGISTRADA", repositorio: _RepositorioFalso | None = None
) -> tuple[RegistrarCartaGarantia, _RepositorioFalso, _RegistroEventosFalso]:
    repositorio = repositorio or _RepositorioFalso()
    registro = _RegistroEventosFalso()
    return (
        RegistrarCartaGarantia(repositorio, _EstadoFijo(estado), registro, _RelojFijo()),
        repositorio,
        registro,
    )


async def prueba_registra_la_carta_y_su_evento() -> None:
    caso_uso, repositorio, registro = _caso_uso()
    carta = await caso_uso.ejecutar(3, _DATOS, actor="ana.analista")

    assert repositorio.cartas[3] == carta
    assert carta.registrado_por == "ana.analista"
    (evento,) = registro.eventos
    assert evento.tipo_evento == "CARTA_GARANTIA_REGISTRADA"
    assert evento.datos == {
        "numero": "CG-2026-0001",
        "vigente_hasta": "2026-11-30",
        "monto": "1500.00",
    }


@pytest.mark.parametrize(
    "datos",
    [
        DatosCartaGarantia(" ", date(2026, 11, 1), date(2026, 11, 30), Decimal("10")),
        DatosCartaGarantia("CG-1", date(2026, 11, 30), date(2026, 11, 1), Decimal("10")),
        DatosCartaGarantia("CG-1", date(2026, 11, 1), date(2026, 11, 30), Decimal("0")),
    ],
)
async def prueba_rechaza_datos_incoherentes(datos: DatosCartaGarantia) -> None:
    caso_uso, _, _ = _caso_uso()
    with pytest.raises(ErrorCartaGarantiaInvalida):
        await caso_uso.ejecutar(3, datos, actor="ana.analista")


async def prueba_una_sola_carta_por_cuenta() -> None:
    caso_uso, repositorio, _ = _caso_uso()
    await caso_uso.ejecutar(3, _DATOS, actor="ana.analista")
    with pytest.raises(ErrorCartaGarantiaYaRegistrada):
        await caso_uso.ejecutar(3, _DATOS, actor="ana.analista")


@pytest.mark.parametrize("estado", ["CERRADA", "ANULADA"])
async def prueba_no_se_registra_en_una_cuenta_cerrada(estado: str) -> None:
    caso_uso, _, _ = _caso_uso(estado)
    with pytest.raises(ErrorCuentaSinRegistroCarta):
        await caso_uso.ejecutar(3, _DATOS, actor="ana.analista")


async def prueba_cuenta_inexistente() -> None:
    caso_uso, _, _ = _caso_uso(None)
    with pytest.raises(ErrorCuentaInexistenteCarta):
        await caso_uso.ejecutar(3, _DATOS, actor="ana.analista")


async def prueba_el_aviso_de_vigencia_usa_la_carta_registrada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "REGISTRADA")
        hasta = (_AHORA + timedelta(days=3)).date()
        await RepositorioCartaGarantiaSql(sesion).guardar(
            CartaGarantia(
                cuenta_medica_id=cuenta_id,
                numero="CG-9",
                vigente_desde=_AHORA.date(),
                vigente_hasta=hasta,
                monto=Decimal("200.00"),
                registrado_en=_AHORA,
                registrado_por="ana.analista",
            )
        )
        await sesion.commit()

        hitos = await RepositorioPlazosSql(sesion, 5).cuentas_con_carta_garantia_por_vencer()
        (hito,) = [h for h in hitos if h.cuenta_medica_id == cuenta_id]
        assert hito.vigente_hasta == hasta
        assert hito.ya_avisada is False
