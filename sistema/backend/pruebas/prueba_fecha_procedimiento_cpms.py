"""La fecha del procedimiento confirmado: no posterior a hoy y no anterior
a la prestacion de la cuenta (al ingreso, en una hospitalizacion)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.dominio.cpms.casos_uso import ConfirmacionCodigoCpms, ConfirmarCodigoCpms
from app.dominio.cpms.puertos import ErrorProcedimientoInvalido
from pruebas import prueba_casos_uso_cpms as cpms

_HOY = date(2026, 9, 16)
_INICIO = datetime(2026, 9, 16, 10, 0, 0)


def _confirmar(fecha_minima: date | None) -> tuple[ConfirmarCodigoCpms, cpms._RepositorioFalso]:
    repositorio = cpms._RepositorioFalso(
        codigos_existentes={"99201": cpms._candidato("99201")}, fecha_minima=fecha_minima
    )
    caso_uso = ConfirmarCodigoCpms(
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=cpms._RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=cpms._RelojFijo(datetime(2026, 9, 16, 10, 5, 0)),
    )
    return caso_uso, repositorio


def _con_fecha(fecha: date) -> ConfirmacionCodigoCpms:
    return ConfirmacionCodigoCpms(
        cuenta_medica_id=7,
        descripcion_registrada="consulta",
        codigo_elegido="99201",
        posicion_aceptada=None,
        usuario_confirmo_id=3,
        cantidad=1,
        monto_unitario=Decimal("1.00"),
        fecha=fecha,
    )


async def prueba_fecha_de_hoy_se_acepta() -> None:
    caso_uso, repositorio = _confirmar(date(2026, 9, 10))
    await caso_uso.ejecutar(_con_fecha(_HOY), actor="prueba", inicio_sugerencia=_INICIO)
    assert len(repositorio.confirmaciones) == 1


async def prueba_fecha_igual_a_la_prestacion_se_acepta() -> None:
    caso_uso, repositorio = _confirmar(date(2026, 9, 10))
    await caso_uso.ejecutar(
        _con_fecha(date(2026, 9, 10)), actor="prueba", inicio_sugerencia=_INICIO
    )
    assert len(repositorio.confirmaciones) == 1


async def prueba_fecha_posterior_a_hoy_se_rechaza() -> None:
    caso_uso, repositorio = _confirmar(date(2026, 9, 10))
    with pytest.raises(ErrorProcedimientoInvalido, match="posterior a hoy"):
        await caso_uso.ejecutar(
            _con_fecha(date(2026, 9, 17)), actor="prueba", inicio_sugerencia=_INICIO
        )
    assert repositorio.confirmaciones == []


async def prueba_fecha_anterior_a_la_prestacion_se_rechaza() -> None:
    caso_uso, repositorio = _confirmar(date(2026, 9, 10))
    with pytest.raises(ErrorProcedimientoInvalido, match="anterior a la prestacion"):
        await caso_uso.ejecutar(
            _con_fecha(date(2026, 9, 9)), actor="prueba", inicio_sugerencia=_INICIO
        )
    assert repositorio.confirmaciones == []
