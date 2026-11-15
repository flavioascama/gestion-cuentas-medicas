"""Prueba el cargador de selectores (Seccion 8.1) contra el archivo real
configuracion/selectores/acredita_salud.yaml del backend -- si alguien le
cambia una clave sin actualizar el robot, esta prueba lo detecta antes que
un fallo en Docker."""

from __future__ import annotations

import pytest

from trabajador.soporte.selectores import ErrorSelectorNoEncontrado, obtener_selector


@pytest.mark.parametrize(
    ("seccion", "clave"),
    [
        ("ingreso", "campo_usuario"),
        ("ingreso", "campo_clave"),
        ("ingreso", "boton_ingresar"),
        ("consulta_iafas", "ruta"),
        ("consulta_iafas", "campo_tipo_documento"),
        ("consulta_iafas", "campo_numero_documento"),
        ("consulta_iafas", "boton_buscar"),
        ("consulta_iafas", "no_encontrado"),
        ("consulta_iafas", "enlace_acreditar"),
        ("consulta_iafas", "plan"),
        ("consulta_iafas", "vigente_desde"),
        ("consulta_iafas", "vigente_hasta"),
        ("consulta_iafas", "preexistencias"),
        ("evaluacion", "condicion_cobertura"),
        ("evaluacion", "tipo_copago"),
        ("evaluacion", "monto_copago_fijo"),
        ("evaluacion", "porcentaje_coaseguro"),
        ("evaluacion", "boton_generar"),
        ("documento", "codigo_autorizacion"),
    ],
)
def prueba_todos_los_selectores_que_usa_el_robot_existen(seccion: str, clave: str) -> None:
    valor = obtener_selector(seccion, clave)
    assert valor


def prueba_selector_inexistente_falla_con_mensaje_explicito() -> None:
    with pytest.raises(ErrorSelectorNoEncontrado):
        obtener_selector("seccion_que_no_existe", "clave_que_no_existe")
