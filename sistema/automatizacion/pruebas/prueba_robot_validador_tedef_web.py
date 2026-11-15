"""Pruebas de las funciones puras del robot del validador TEDEF Web
(Seccion 8.3, Fase 16): parseo de los reportes .xlsx que descarga (mismo
formato que app/reportes.py del simulador, Seccion 9.2) y del nombre de
archivo en la cabecera Content-Disposition."""

from __future__ import annotations

import io

import openpyxl

from trabajador.robots.robot_validador_tedef_web import (
    _nombre_adjunto,
    _parsear_reporte_detallada,
    _parsear_reporte_forma,
)


def _libro(
    filas_encabezado: list[list[object]], filas_columnas: list[object], filas: list[tuple]
) -> bytes:
    """Reproduce la forma exacta de los reportes del simulador: siete
    filas de encabezado libre, la fila con los nombres de columna, y las
    filas de datos (ver app/reportes.py de simuladores/tedef_web)."""

    libro = openpyxl.Workbook()
    hoja = libro.active
    assert hoja is not None
    for fila in filas_encabezado:
        hoja.append(fila)
    hoja.append(filas_columnas)
    for fila in filas:
        hoja.append(list(fila))
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


_ENCABEZADO = [
    ["IPRESS: Clinica Pardo S.A.C. (15995250)"],
    ["IAFAS: 96969"],
    ["Lote: 0000004"],
    ["Usuario: validador_ipress_demo"],
    ["Perfil: TEDEF-Validador-IPRESS"],
    ["Codigos SIM-*: no oficiales, propios de este simulador (Seccion 9.2)."],
    [],
]


def prueba_parsear_reporte_forma_lee_las_filas_de_datos() -> None:
    contenido = _libro(
        _ENCABEZADO,
        ["Tabla", "Codigo de error", "Descripcion"],
        [("T1", "SIM-001", "Codigo de IPRESS no asignado al usuario.")],
    )

    observaciones = _parsear_reporte_forma(contenido)

    assert len(observaciones) == 1
    assert observaciones[0].tabla == "T1"
    assert observaciones[0].numero_linea is None
    assert observaciones[0].codigo_error == "SIM-001"
    assert observaciones[0].descripcion == "Codigo de IPRESS no asignado al usuario."


def prueba_parsear_reporte_forma_trata_guion_como_tabla_ausente() -> None:
    contenido = _libro(
        _ENCABEZADO,
        ["Tabla", "Codigo de error", "Descripcion"],
        [("-", "SIM-002", "Lote ya registrado antes.")],
    )

    observaciones = _parsear_reporte_forma(contenido)

    assert observaciones[0].tabla is None


def prueba_parsear_reporte_detallada_lee_las_nueve_columnas() -> None:
    contenido = _libro(
        _ENCABEZADO,
        [
            "IPRESS/IAFAS",
            "Lote",
            "Tabla",
            "Numero de linea",
            "Campo clave",
            "Campo",
            "Valor observado",
            "Codigo de error",
            "Descripcion",
        ],
        [
            (
                "15995250/96969",
                "0000004",
                "T2",
                3,
                "20260925",
                "Fecha de Atencion",
                "20261301",
                "SIM-FECHA",
                "Fecha invalida.",
            )
        ],
    )

    observaciones = _parsear_reporte_detallada(contenido)

    assert len(observaciones) == 1
    obs = observaciones[0]
    assert obs.tabla == "T2"
    assert obs.numero_linea == 3
    assert obs.campo_clave == "20260925"
    assert obs.campo == "Fecha de Atencion"
    assert obs.valor_observado == "20261301"
    assert obs.codigo_error == "SIM-FECHA"
    assert obs.descripcion == "Fecha invalida."


def prueba_parsear_reporte_detallada_sin_observaciones_devuelve_vacio() -> None:
    contenido = _libro(
        _ENCABEZADO,
        [
            "IPRESS/IAFAS",
            "Lote",
            "Tabla",
            "Numero de linea",
            "Campo clave",
            "Campo",
            "Valor observado",
            "Codigo de error",
            "Descripcion",
        ],
        [],
    )

    assert _parsear_reporte_detallada(contenido) == ()


def prueba_nombre_adjunto_extrae_el_filename() -> None:
    encabezado = 'attachment; filename="937_20690951848_15995250_96969_0000004_202609_20260925.S01"'
    assert (
        _nombre_adjunto(encabezado) == "937_20690951848_15995250_96969_0000004_202609_20260925.S01"
    )


def prueba_nombre_adjunto_sin_encabezado_devuelve_none() -> None:
    assert _nombre_adjunto(None) is None
    assert _nombre_adjunto("") is None


def prueba_nombre_adjunto_sin_filename_devuelve_none() -> None:
    assert _nombre_adjunto("attachment") is None
