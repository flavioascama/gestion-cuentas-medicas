"""Registro de cobertura en contingencia con plan y copago: se guarda con
los mismos valores que deja el robot ('fijo' con monto, 'coaseguro' con
porcentaje, o sin copago)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.esquemas_contingencia import SolicitudCoberturaContingencia
from app.api.rutas_contingencia import resultado_contingencia
from app.dominio.contingencia.errores import ErrorCopagoIncompleto


def _solicitud(**cambios: object) -> SolicitudCoberturaContingencia:
    datos: dict[str, object] = {
        "condicion_cobertura": "ACREDITABLE",
        "codigo_autorizacion": "AUT1",
        "tipo_documento_autorizacion": "01",
        "codigo_asegurado": "00012-1",
        "tipo_afiliacion": "1",
        "sustento": "Constancia telefonica de la IAFAS",
    }
    datos.update(cambios)
    return SolicitudCoberturaContingencia.model_validate(datos)


def prueba_sin_copago_y_sin_plan() -> None:
    resultado = resultado_contingencia(_solicitud(monto_copago_fijo="10.00"))
    assert (resultado.tipo_copago, resultado.monto_copago_fijo) == (None, None)
    assert resultado.porcentaje_coaseguro is None
    assert resultado.plan is None


def prueba_copago_de_monto_fijo_con_plan() -> None:
    resultado = resultado_contingencia(
        _solicitud(tipo_copago="fijo", monto_copago_fijo="25.50", plan=" PLAN A ")
    )
    assert resultado.tipo_copago == "fijo"
    assert resultado.monto_copago_fijo == Decimal("25.50")
    assert resultado.porcentaje_coaseguro is None
    assert resultado.plan == "PLAN A"


def prueba_coaseguro() -> None:
    resultado = resultado_contingencia(
        _solicitud(tipo_copago="coaseguro", porcentaje_coaseguro=20, monto_copago_fijo="5")
    )
    assert resultado.tipo_copago == "coaseguro"
    assert resultado.porcentaje_coaseguro == 20
    assert resultado.monto_copago_fijo is None


@pytest.mark.parametrize("tipo", ["fijo", "coaseguro"])
def prueba_copago_sin_valor_se_rechaza(tipo: str) -> None:
    with pytest.raises(ErrorCopagoIncompleto):
        resultado_contingencia(_solicitud(tipo_copago=tipo))
