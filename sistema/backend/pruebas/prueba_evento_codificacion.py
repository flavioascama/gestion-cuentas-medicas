"""Codificar deja registro en el historial (2026-11-19): el evento
PROCEDIMIENTO_CODIFICADO, con los mismos datos que PROCEDIMIENTO_RETIRADO
mas la posicion aceptada de la sugerencia, sin descripcion clinica,
diagnostico ni datos del paciente."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.dominio.cpms.casos_uso import ConfirmacionCodigoCpms, ConfirmarCodigoCpms
from app.dominio.cpms.puertos import ErrorCodigoCpmsInexistente
from pruebas import prueba_casos_uso_cpms as cpms


def _confirmacion(codigo: str, posicion: int | None) -> ConfirmacionCodigoCpms:
    return ConfirmacionCodigoCpms(
        cuenta_medica_id=7,
        descripcion_registrada="Consulta ambulatoria de control",
        codigo_elegido=codigo,
        posicion_aceptada=posicion,
        usuario_confirmo_id=3,
        cantidad=1,
        monto_unitario=Decimal("50.00"),
        fecha=date(2026, 9, 16),
    )


def _caso_uso() -> tuple[ConfirmarCodigoCpms, cpms._RegistroEventosFalso]:
    registro = cpms._RegistroEventosFalso()
    caso_uso = ConfirmarCodigoCpms(
        repositorio=cpms._RepositorioFalso(  # type: ignore[arg-type]
            codigos_existentes={"99201": cpms._candidato("99201")}
        ),
        registro_mediciones=cpms._RegistroMedicionesFalso(),
        reloj=cpms._RelojFijo(datetime(2026, 9, 16, 10, 5, 0)),
        estado_cuenta=cpms._EstadoCuentaFijo("REGISTRADA"),
        registro_eventos=registro,
    )
    return caso_uso, registro


@pytest.mark.parametrize("posicion", [2, None])
async def prueba_confirmar_un_codigo_deja_su_evento(posicion: int | None) -> None:
    caso_uso, registro = _caso_uso()

    procedimiento_id = await caso_uso.ejecutar(
        _confirmacion("99201", posicion), "carlos.auditor", datetime(2026, 9, 16, 10, 0, 0)
    )

    (evento,) = registro.eventos
    assert (evento.tipo_evento, evento.actor, evento.cuenta_medica_id) == (
        "PROCEDIMIENTO_CODIFICADO",
        "carlos.auditor",
        7,
    )
    assert (evento.estado_previo, evento.estado_nuevo) == (None, None)
    assert evento.datos == {
        "procedimiento_id": procedimiento_id,
        "codigo_asignado": "99201",
        "posicion_aceptada": posicion,
    }


async def prueba_un_codigo_rechazado_no_deja_evento() -> None:
    caso_uso, registro = _caso_uso()

    with pytest.raises(ErrorCodigoCpmsInexistente):
        await caso_uso.ejecutar(
            _confirmacion("00000", 1), "carlos.auditor", datetime(2026, 9, 16, 10, 0, 0)
        )

    assert registro.eventos == []
