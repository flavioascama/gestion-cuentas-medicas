"""Nueva solicitud de la validacion de un lote ya cargado en TEDEF Web:
el robot consulta en que punto quedo en lugar de fallar o duplicarlo."""

from __future__ import annotations

import pytest

from trabajador.robots.robot_validador_tedef_web import (
    ACCION_ESPERAR,
    ACCION_NO_ENCONTRADO,
    ACCION_VALIDAR,
    ACCION_YA_VALIDADO,
    accion_al_validar,
)


def prueba_un_lote_registrado_se_manda_a_validar() -> None:
    assert accion_al_validar("REGISTRADO", en_por_enviar=False) == ACCION_VALIDAR


@pytest.mark.parametrize("estado", ["VALIDANDO", "OBSERVADO_DETALLADA"])
def prueba_un_lote_en_validacion_u_observado_solo_se_lee(estado: str) -> None:
    assert accion_al_validar(estado, en_por_enviar=False) == ACCION_ESPERAR


def prueba_un_lote_que_ya_paso_a_por_enviar_esta_validado() -> None:
    assert accion_al_validar(None, en_por_enviar=True) == ACCION_YA_VALIDADO


def prueba_un_lote_que_no_esta_en_ninguna_lista_no_se_encuentra() -> None:
    assert accion_al_validar(None, en_por_enviar=False) == ACCION_NO_ENCONTRADO
