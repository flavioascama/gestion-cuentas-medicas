"""Reportes .xlsx (Seccion 9.2: "con la cabecera y las columnas del
manual (IPRESS/IAFAS, lote, tabla, numero de linea, campo clave, campo,
valor observado, codigo de error, descripcion). Codigos con prefijo SIM-,
documentados como no oficiales")."""

from __future__ import annotations

import io
from dataclasses import dataclass

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from app.criterios_simulados import DominioSimulado
from app.datos import IpressPropia
from app.revision_forma import ObservacionForma
from app.validacion_detallada import ObservacionDetallada


@dataclass(frozen=True, slots=True)
class EncabezadoReporte:
    ipress: IpressPropia
    codigo_iafas: str
    numero_lote: str
    usuario: str
    perfil: str


def _escribir_encabezado(hoja: Worksheet, encabezado: EncabezadoReporte) -> None:
    hoja.append([f"IPRESS: {encabezado.ipress.razon_social} ({encabezado.ipress.codigo_ipress})"])
    hoja.append([f"IAFAS: {encabezado.codigo_iafas}"])
    hoja.append([f"Lote: {encabezado.numero_lote}"])
    hoja.append([f"Usuario: {encabezado.usuario}"])
    hoja.append([f"Perfil: {encabezado.perfil}"])
    hoja.append(["Codigos SIM-*: no oficiales, propios de este simulador (Seccion 9.2)."])
    hoja.append([])


def _libro_con_encabezado(
    titulo: str, encabezado: EncabezadoReporte
) -> tuple[openpyxl.Workbook, Worksheet]:
    libro = openpyxl.Workbook()
    hoja = libro.active
    assert hoja is not None
    hoja.title = titulo
    _escribir_encabezado(hoja, encabezado)
    return libro, hoja


def _bytes_de(libro: openpyxl.Workbook) -> bytes:
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def generar_reporte_observaciones_forma(
    encabezado: EncabezadoReporte, observaciones: tuple[ObservacionForma, ...]
) -> bytes:
    libro, hoja = _libro_con_encabezado("Observaciones", encabezado)
    hoja.append(["Tabla", "Codigo de error", "Descripcion"])
    for obs in observaciones:
        hoja.append([obs.tabla or "-", obs.codigo_error, obs.descripcion])
    return _bytes_de(libro)


def generar_reporte_validacion_detallada(
    encabezado: EncabezadoReporte, observaciones: list[ObservacionDetallada]
) -> bytes:
    libro, hoja = _libro_con_encabezado("Error de Validacion", encabezado)
    ipress_iafas = f"{encabezado.ipress.codigo_ipress}/{encabezado.codigo_iafas}"
    hoja.append(
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
        ]
    )
    for obs in observaciones:
        hoja.append(
            [
                ipress_iafas,
                encabezado.numero_lote,
                obs.tabla,
                obs.numero_linea,
                obs.campo_clave,
                obs.campo,
                obs.valor_observado,
                obs.codigo_error,
                obs.descripcion,
            ]
        )
    return _bytes_de(libro)


def generar_excel_dominio(dominio: DominioSimulado) -> bytes:
    """ "Descargar Excel" de Tablas de Validacion (Seccion 9.2, punto 7)."""

    libro = openpyxl.Workbook()
    hoja = libro.active
    assert hoja is not None
    hoja.title = dominio.nombre[:31]
    hoja.append([f"{dominio.tabla} — {dominio.nombre}"])
    hoja.append(["Valor"])
    for valor in sorted(dominio.valores):
        hoja.append([valor])
    return _bytes_de(libro)


def generar_reporte_clave_valor(encabezado: EncabezadoReporte, motivo: str) -> bytes:
    """ "Error de Clave Valor-XLS" (Seccion 9.2, Lotes por Enviar): control
    de duplicidad al enviar un lote que ya fue enviado antes."""

    libro, hoja = _libro_con_encabezado("Error de Clave Valor", encabezado)
    hoja.append(["Codigo de error", "Descripcion"])
    hoja.append(["SIM-DUP-ENV", motivo])
    return _bytes_de(libro)
