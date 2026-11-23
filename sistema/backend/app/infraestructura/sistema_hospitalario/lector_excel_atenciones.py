"""Lectura del Excel con el que el administrador carga atenciones del
sistema hospitalario: una hoja de atenciones, una de procedimientos y una de
farmacia, unidas por el codigo de la atencion. Cada atencion queda en el
mismo formato que entrega el sistema hospitalario (esquema_atencion.py)."""

from __future__ import annotations

import zipfile
from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import ValidationError

from app.compartido.archivo_catalogo import ErrorArchivoCatalogoInvalido
from app.infraestructura.sistema_hospitalario.esquema_atencion import AtencionJson

_CODIGO = "Codigo de atencion"
# hoja -> encabezados, en el orden de la plantilla.
HOJAS: dict[str, tuple[str, ...]] = {
    "Atenciones": (
        _CODIGO,
        "Tipo de atencion",
        "Fecha de prestacion",
        "Hora de prestacion",
        "Historia clinica",
        "Tipo de documento",
        "Numero de documento",
        "Nombres",
        "Apellidos",
        "Codigo de IAFAS",
        "Colegiatura del medico",
        "Nombre del medico",
        "Diagnostico principal",
        "Diagnosticos secundarios",
        "Fecha de ingreso",
        "Fecha de alta",
        "Copago cobrado",
        "Referencia del copago",
        "Fecha del copago",
    ),
    "Procedimientos": (
        _CODIGO,
        "Descripcion",
        "Area",
        "Cantidad",
        "Monto unitario",
        "Fecha",
    ),
    "Farmacia": (
        _CODIGO,
        "Codigo del producto",
        "Cantidad",
        "Tipo de unidad",
        "Monto unitario",
        "Fecha de dispensacion",
    ),
}
_EJEMPLO: dict[str, tuple[object, ...]] = {
    "Atenciones": (
        "AT-2026-000201",
        "AMBULATORIA",
        "2026-11-20",
        "09:30:00",
        "00045871",
        "1",
        "81953443",
        "Elvira",
        "Ochoa Cañas",
        "99553",
        "045871",
        "Luis Paredes Soto",
        "J00X",
        "",
        "",
        "",
        "",
        "",
        "",
    ),
    "Procedimientos": (
        "AT-2026-000201",
        "Consulta ambulatoria para la evaluacion y manejo de un usuario de salud nuevo",
        "PROCEDIMIENTO",
        1,
        "80.00",
        "2026-11-20",
    ),
    "Farmacia": ("AT-2026-000201", "008400001344", 2, "1", "12.50", "2026-11-20"),
}


def plantilla_xlsx() -> bytes:
    """El Excel vacio con los encabezados y una atencion de ejemplo."""
    libro = openpyxl.Workbook(write_only=True)
    for nombre, encabezados in HOJAS.items():
        hoja = libro.create_sheet(nombre)
        hoja.append(list(encabezados))
        hoja.append(list(_EJEMPLO[nombre]))
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat() if valor.time() == time(0) else valor.isoformat()
    if isinstance(valor, date | time):
        return valor.isoformat()
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _filas(libro: Any, nombre: str) -> list[dict[str, str]]:
    """Las filas con datos de una hoja, como encabezado -> texto."""
    if nombre not in libro.sheetnames:
        raise ErrorArchivoCatalogoInvalido(f"Falta la hoja '{nombre}'.")
    filas = list(libro[nombre].iter_rows(values_only=True))
    posiciones = {_texto(celda): i for i, celda in enumerate(filas[0])} if filas else {}
    faltantes = [e for e in HOJAS[nombre] if e not in posiciones]
    if faltantes:
        raise ErrorArchivoCatalogoInvalido(
            f"Hoja '{nombre}': faltan las columnas {', '.join(faltantes)}."
        )
    resultado = []
    for fila in filas[1:]:
        datos = {e: _texto(fila[posiciones[e]]) for e in HOJAS[nombre]}
        if any(datos.values()):
            resultado.append(datos)
    return resultado


def _detalle(
    filas: list[dict[str, str]], codigo: str, campos: dict[str, str]
) -> list[dict[str, str]]:
    return [
        {campo: fila[encabezado] for encabezado, campo in campos.items()}
        for fila in filas
        if fila[_CODIGO] == codigo
    ]


_PROCEDIMIENTO = {
    "Descripcion": "descripcion",
    "Area": "area",
    "Cantidad": "cantidad",
    "Monto unitario": "monto_unitario",
    "Fecha": "fecha",
}
_PRODUCTO = {
    "Codigo del producto": "codigo_producto",
    "Cantidad": "cantidad",
    "Tipo de unidad": "tipo_unidad_dispensacion",
    "Monto unitario": "monto_unitario",
    "Fecha de dispensacion": "fecha_dispensacion",
}


def _atencion(
    fila: dict[str, str], procedimientos: list[dict[str, str]], farmacia: list[dict[str, str]]
) -> dict[str, Any]:
    codigo = fila[_CODIGO]
    hospitalizacion = None
    if fila["Fecha de ingreso"] or fila["Fecha de alta"]:
        hospitalizacion = {
            "fecha_ingreso": fila["Fecha de ingreso"] or None,
            "fecha_alta": fila["Fecha de alta"] or None,
        }
    copago = None
    if fila["Copago cobrado"]:
        copago = {
            "monto": fila["Copago cobrado"],
            "referencia": fila["Referencia del copago"],
            "fecha": fila["Fecha del copago"] or fila["Fecha de prestacion"],
        }
    return {
        "atencion_id": codigo,
        "tipo_atencion": fila["Tipo de atencion"].upper(),
        "fecha_prestacion": fila["Fecha de prestacion"],
        "hora_prestacion": fila["Hora de prestacion"],
        "numero_historia_clinica": fila["Historia clinica"],
        "paciente": {
            "tipo_documento": fila["Tipo de documento"],
            "numero_documento": fila["Numero de documento"],
            "nombres": fila["Nombres"],
            "apellidos": fila["Apellidos"],
        },
        "iafas_codigo": fila["Codigo de IAFAS"],
        "profesional": {
            "numero_colegiatura": fila["Colegiatura del medico"],
            "nombres": fila["Nombre del medico"],
        },
        "diagnostico_principal_cie10": fila["Diagnostico principal"],
        "diagnosticos_secundarios_cie10": [
            d.strip() for d in fila["Diagnosticos secundarios"].split(",") if d.strip()
        ],
        "hospitalizacion": hospitalizacion,
        "procedimientos": _detalle(procedimientos, codigo, _PROCEDIMIENTO),
        "farmacia": _detalle(farmacia, codigo, _PRODUCTO),
        "copago_cobrado": copago,
    }


def leer_atenciones_xlsx(contenido: bytes) -> list[AtencionJson]:
    try:
        libro = openpyxl.load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError) as error:
        raise ErrorArchivoCatalogoInvalido("El archivo no es un Excel .xlsx válido.") from error
    atenciones = _filas(libro, "Atenciones")
    procedimientos = _filas(libro, "Procedimientos")
    farmacia = _filas(libro, "Farmacia")
    if not atenciones:
        raise ErrorArchivoCatalogoInvalido("La hoja 'Atenciones' no tiene atenciones.")
    resultado: list[AtencionJson] = []
    for fila in atenciones:
        codigo = fila[_CODIGO] or "(sin código)"
        try:
            resultado.append(AtencionJson.model_validate(_atencion(fila, procedimientos, farmacia)))
        except ValidationError as error:
            campo = ".".join(str(parte) for parte in error.errors()[0]["loc"])
            raise ErrorArchivoCatalogoInvalido(
                f"Atención {codigo}: falta un dato o no es válido ({campo})."
            ) from error
    codigos = [a.atencion_id for a in resultado]
    repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
    if repetidos:
        raise ErrorArchivoCatalogoInvalido(
            f"El archivo repite el código de atención {', '.join(repetidos)}."
        )
    return resultado
