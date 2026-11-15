"""Las pruebas de obligatoriedad/tipo/dominio usan una Tabla Anexo1
sintetica y pequena (mas facil de controlar). Las de llaves entre tablas
usan la fixture `tablas_anexo1` (el Anexo 1 real): `_validar_llaves_entre_
tablas` busca los campos 5, 6 y 11 por numero -- las posiciones reales de
"Correlativo de la prestacion" y "Cantidad de prestaciones..." -- por lo
que una tabla sintetica con otra numeracion no ejercitaria ese codigo."""

from __future__ import annotations

from app.anexo1 import CampoAnexo1, TablaAnexo1
from app.criterios_simulados import DominioSimulado
from app.validacion_detallada import validar_detallada

_T1 = TablaAnexo1(
    id="T1",
    prefijo="dfac",
    longitud_registro=15,
    campos=(
        CampoAnexo1(
            1, "Numero de Lote", True, 7, 1, "Solo contiene caracteres entre el rango [0 al 9]"
        ),
        CampoAnexo1(2, "Fecha de envio", True, 8, 8, "La fecha debe ser valida."),
    ),
)
_T2 = TablaAnexo1(
    id="T2",
    prefijo="date",
    longitud_registro=6,
    campos=(
        CampoAnexo1(1, "Correlativo de la prestacion", True, 3, 1, "rango numerico"),
        CampoAnexo1(2, "Servicio", False, 3, 4, "uno de los valores definidos"),
    ),
)
_T3 = TablaAnexo1(
    id="T3",
    prefijo="dser",
    longitud_registro=3,
    campos=(CampoAnexo1(1, "Correlativo de la prestacion", True, 3, 1, "rango numerico"),),
)
_TABLAS = {"T1": _T1, "T2": _T2, "T3": _T3}


def prueba_sin_observaciones_cuando_todo_es_valido() -> None:
    lineas = {"T1": ["0000001" + "20260601"], "T2": ["001" + "ABC"], "T3": ["001"]}
    observaciones = validar_detallada(lineas, _TABLAS, ())
    assert observaciones == []


def prueba_observa_campo_obligatorio_en_blanco() -> None:
    lineas = {"T1": ["       " + "        "], "T2": [], "T3": []}
    observaciones = validar_detallada(lineas, _TABLAS, ())
    codigos = {o.codigo_error for o in observaciones}
    assert "SIM-OBL" in codigos


def prueba_observa_formato_de_fecha_invalido() -> None:
    lineas = {"T1": ["0000001" + "20261301"], "T2": [], "T3": []}  # mes 13 no existe
    observaciones = validar_detallada(lineas, _TABLAS, ())
    assert any(o.codigo_error == "SIM-TIPO" and o.campo == "Fecha de envio" for o in observaciones)


def prueba_observa_dominio_fuera_del_subconjunto_simulado() -> None:
    dominio = DominioSimulado(tabla="T2", campo=2, nombre="Servicio", valores=frozenset({"ABC"}))
    lineas = {"T1": [], "T2": ["001" + "XYZ"], "T3": []}
    observaciones = validar_detallada(lineas, _TABLAS, (dominio,))
    assert any(o.codigo_error == "SIM-DOM" for o in observaciones)


def _linea_real(
    tablas_anexo1: dict[str, TablaAnexo1], tabla_id: str, valores: dict[int, str]
) -> str:
    """Construye una linea del largo real de `tabla_id`, con los campos de
    `valores` en su posicion real y el resto en blanco."""

    tabla = tablas_anexo1[tabla_id]
    partes = [" " * tabla.longitud_registro]
    linea = list(partes[0])
    for campo in tabla.campos:
        valor = valores.get(campo.numero, "")
        segmento = valor.ljust(campo.longitud)[: campo.longitud]
        inicio = campo.posicion_inicial - 1
        linea[inicio : inicio + campo.longitud] = segmento
    return "".join(linea)


def prueba_llave_t2_correlativo_no_puede_superar_cantidad_de_t1(
    tablas_anexo1: dict[str, TablaAnexo1],
) -> None:
    t1 = _linea_real(tablas_anexo1, "T1", {11: "1"})  # cantidad de prestaciones = 1
    t2 = _linea_real(tablas_anexo1, "T2", {5: "2"})  # correlativo = 2, supera la cantidad
    observaciones = validar_detallada({"T1": [t1], "T2": [t2]}, tablas_anexo1, ())
    assert any(o.codigo_error == "SIM-REL" and o.tabla == "T2" for o in observaciones)


def prueba_llave_t3_debe_existir_en_t2(tablas_anexo1: dict[str, TablaAnexo1]) -> None:
    t2 = _linea_real(tablas_anexo1, "T2", {5: "1"})
    t3 = _linea_real(tablas_anexo1, "T3", {5: "2", 6: "1"})  # no existe prestacion 2 en T2
    observaciones = validar_detallada({"T2": [t2], "T3": [t3]}, tablas_anexo1, ())
    assert any(o.codigo_error == "SIM-REL" and o.tabla == "T3" for o in observaciones)


def prueba_llave_t4_debe_existir_en_t2(tablas_anexo1: dict[str, TablaAnexo1]) -> None:
    t2 = _linea_real(tablas_anexo1, "T2", {5: "1"})
    t4 = _linea_real(tablas_anexo1, "T4", {5: "2", 6: "1"})  # no existe prestacion 2 en T2
    observaciones = validar_detallada({"T2": [t2], "T4": [t4]}, tablas_anexo1, ())
    assert any(o.codigo_error == "SIM-REL" and o.tabla == "T4" for o in observaciones)
