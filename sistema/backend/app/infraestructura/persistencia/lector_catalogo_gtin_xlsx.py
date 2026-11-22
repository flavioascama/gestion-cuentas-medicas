"""Lectura del Excel con el que el administrador carga una version del
catalogo GTIN: una hoja, una fila de encabezados y una fila por producto,
con los mismos datos que cada producto de `catalogo_gtin.yaml`."""

from __future__ import annotations

import zipfile
from io import BytesIO

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from app.compartido.archivo_catalogo import ErrorArchivoCatalogoInvalido

# encabezado del Excel -> campo del producto, con el largo maximo de su columna.
_COLUMNAS: dict[str, tuple[str, int]] = {
    "Codigo GTIN": ("codigo", 13),
    "Tipo de codigo": ("tipo_codigo", 10),
    "Tipo de producto del catalogo": ("tipo_producto_catalogo", 50),
    "Tipo de producto TEDEF": ("tipo_producto_tedef", 1),
    "Nombre": ("nombre", 200),
    "Denominacion comun": ("denominacion_comun", 200),
    "Concentracion": ("concentracion", 50),
    "Forma farmaceutica": ("forma_farmaceutica", 50),
}
_OPCIONALES = {"concentracion", "forma_farmaceutica"}
_TIPOS_TEDEF = "MPIRBA"
_NOMBRES_TIPOS_TEDEF = (
    "M (medicamento), P (suplemento dietético o producto natural), "
    "I (insumo o dispositivo médico), R (preparado magistral), "
    "B (producto sanitario o cosmético) o A (suplemento alimenticio)"
)


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def _leer_filas(contenido: bytes) -> list[tuple[object, ...]]:
    try:
        libro = openpyxl.load_workbook(BytesIO(contenido), read_only=True, data_only=True)
        return list(libro.worksheets[0].iter_rows(values_only=True))
    except (zipfile.BadZipFile, InvalidFileException, IndexError, KeyError) as error:
        raise ErrorArchivoCatalogoInvalido("El archivo no es un Excel .xlsx válido.") from error


def _validar_producto(producto: dict[str, object], numero_fila: int) -> None:
    for encabezado, (campo, largo) in _COLUMNAS.items():
        valor = str(producto[campo] or "")
        if not valor and campo not in _OPCIONALES:
            raise ErrorArchivoCatalogoInvalido(f"Fila {numero_fila}: falta '{encabezado}'.")
        if len(valor) > largo:
            raise ErrorArchivoCatalogoInvalido(
                f"Fila {numero_fila}: '{encabezado}' pasa de {largo} caracteres."
            )
    if producto["tipo_producto_tedef"] not in tuple(_TIPOS_TEDEF):
        raise ErrorArchivoCatalogoInvalido(
            f"Fila {numero_fila}: 'Tipo de producto TEDEF' debe ser {_NOMBRES_TIPOS_TEDEF}."
        )


def leer_productos_xlsx_gtin(
    contenido: bytes, nombre_archivo: str
) -> tuple[list[dict[str, object]], dict[str, tuple[str, int]]]:
    """Los productos y, por cada codigo, el archivo y la fila de donde salio."""
    filas = _leer_filas(contenido)
    if not filas:
        raise ErrorArchivoCatalogoInvalido("La hoja está vacía.")
    posiciones = {_texto(celda): i for i, celda in enumerate(filas[0])}
    faltantes = [encabezado for encabezado in _COLUMNAS if encabezado not in posiciones]
    if faltantes:
        raise ErrorArchivoCatalogoInvalido(
            f"Faltan columnas: {', '.join(faltantes)}. Esperadas: {', '.join(_COLUMNAS)}."
        )
    productos: list[dict[str, object]] = []
    trazabilidad: dict[str, tuple[str, int]] = {}
    for numero_fila, fila in enumerate(filas[1:], start=2):
        producto: dict[str, object] = {}
        for encabezado, (campo, _) in _COLUMNAS.items():
            celda = fila[posiciones[encabezado]] if posiciones[encabezado] < len(fila) else None
            if campo == "codigo" and celda is not None and not isinstance(celda, str):
                raise ErrorArchivoCatalogoInvalido(
                    f"Fila {numero_fila}: '{encabezado}' debe ir como texto "
                    "para conservar los ceros."
                )
            producto[campo] = _texto(celda) or None
        if all(valor is None for valor in producto.values()):
            continue
        _validar_producto(producto, numero_fila)
        codigo = str(producto["codigo"])
        if codigo in trazabilidad:
            raise ErrorArchivoCatalogoInvalido(f"Fila {numero_fila}: código repetido {codigo}.")
        trazabilidad[codigo] = (nombre_archivo, numero_fila)
        productos.append(producto)
    if not productos:
        raise ErrorArchivoCatalogoInvalido("El archivo no tiene productos.")
    return productos, trazabilidad
