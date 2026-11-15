"""Excel: lectura del archivo de carga masiva y exportacion del historial
(Seccion 9.1: 'perfil de carga masiva' y 'descarga masiva ... en formato
Excel')."""

from __future__ import annotations

import io

import openpyxl

from app.almacenamiento import Acreditacion


def leer_documentos_carga_masiva(contenido: bytes) -> list[tuple[str, str]]:
    """Espera dos columnas, con encabezado: tipo_documento, numero_documento."""

    libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    hoja = libro.active
    if hoja is None:
        return []
    filas = hoja.iter_rows(values_only=True)
    next(filas, None)  # encabezado
    documentos = []
    for fila in filas:
        if not fila or fila[0] is None:
            continue
        documentos.append((str(fila[0]).strip(), str(fila[1]).strip()))
    return documentos


def generar_excel_historial(acreditaciones: list[Acreditacion]) -> bytes:
    libro = openpyxl.Workbook()
    hoja = libro.active
    assert hoja is not None
    hoja.title = "Historial de acreditaciones"
    hoja.append(
        [
            "Codigo de autorizacion",
            "Tipo de documento",
            "Numero de documento",
            "Asegurado",
            "IAFAS",
            "IPRESS",
            "Condicion de cobertura",
            "Tipo de copago",
            "Monto copago fijo",
            "Porcentaje coaseguro",
            "Generado en",
        ]
    )
    for a in acreditaciones:
        hoja.append(
            [
                a.codigo_autorizacion,
                a.tipo_documento,
                a.numero_documento,
                a.nombre_asegurado,
                a.iafas_codigo,
                a.ipress_codigo,
                a.condicion_cobertura,
                a.tipo_copago,
                a.monto_copago_fijo,
                a.porcentaje_coaseguro,
                a.generado_en,
            ]
        )
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
