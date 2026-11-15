"""Extrae el esquema TEDEF del Anexo 1 (Seccion 7.1) a un YAML versionado.

El sistema en ejecucion lee unicamente el YAML producido por este script,
nunca el .xls (Regla 0.1: el .xls es fuente de solo lectura). Se aborta
con un error explicito si alguna invariante no se cumple: numeracion de
campos no consecutiva, posiciones que no encajan, longitud de tabla
distinta de la verificada en la Fase 1, o total de campos distinto de 218.

La obligatoriedad POR TABLA (distinta de la obligatoriedad por CAMPO, que
si esta en el Anexo 1) no esta en el Anexo 1: se toma de la tabla de
consistencia de tablas de la hoja 'Estandares' del Anexo 3 (filas 57 a 65),
la misma fuente que cita la Seccion 1.2 del plan ("Obligatoriedad segun el
Anexo 3"). Ver docs/DECISIONES.md para el detalle de esta decision y de
las dos anomalias de la columna Decimal que el script solo advierte.

Uso (desde sistema/backend/):
    uv run python herramientas/extraer_esquema_tedef.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from typing import Any

import xlrd
import yaml

from app.compartido.rutas import RAIZ_BACKEND, raiz_docs_fuentes

_CARPETA_FUENTES = raiz_docs_fuentes()
ARCHIVO_ANEXO1 = _CARPETA_FUENTES / "Anexo-1_tedef-ipress-iafas_octubre_2025.xls"
ARCHIVO_ANEXO3 = _CARPETA_FUENTES / "Anexo-3_estandares-de-archivos-de-transmision-electronica.xls"
SALIDA = RAIZ_BACKEND / "configuracion" / "esquema_tedef" / "esquema_2025_10.yaml"

# Verificado en la Fase 1 (docs/DECISIONES.md) contra el propio archivo:
# hoja, prefijo y longitud de registro de cada una de las ocho tablas.
TABLAS_ANEXO1 = [
    ("T1", "T1-Documento Facturador", "dfac", 242),
    ("T2", "T2-Car Gen de la Prestación", "date", 410),
    ("T3", "T3-Detalle de Servicios", "dser", 244),
    ("T4", "T4-Productos de Farmacia", "dfar", 146),
    ("T5", "T5-Dental", "dden", 53),
    ("T6", "T6-Prestación", "dpre", 379),
    ("T7", "T7-Diagnosticos", "ddia", 49),
    ("T8", "T8- Actividades preventivas", "dprv", 64),
]

_PATRON_TITULO_TABLA = re.compile(r"TABLA\s+\d+\s*:\s*(.+)", re.IGNORECASE)
_PATRON_ETIQUETA_TABLA = re.compile(r"Tabla\s+(\d+)", re.IGNORECASE)


def _es_fila_de_campo(valor: Any) -> bool:
    return isinstance(valor, float) and valor == int(valor)


def _obligatorio_de_campo(valor: Any) -> bool:
    normalizado = str(valor).strip().upper()
    if normalizado == "SI":
        return True
    if normalizado == "NO":
        return False
    raise ValueError(f"Valor de 'Obligatorio' de campo no reconocido: {valor!r}")


def _decimales_de_celda(valor: Any, contexto: str) -> int | None:
    if valor == "":
        return None
    if isinstance(valor, float):
        return int(valor)
    print(
        f"ADVERTENCIA: columna Decimal con valor no numerico en {contexto}: "
        f"{valor!r}. Se registra como decimales=null (ver docs/DECISIONES.md).",
        file=sys.stderr,
    )
    return None


def _nombre_de_tabla(hoja: xlrd.sheet.Sheet) -> str:
    titulo = str(hoja.cell_value(0, 0)).strip()
    coincidencia = _PATRON_TITULO_TABLA.match(titulo)
    if not coincidencia:
        raise ValueError(f"No se pudo leer el titulo de tabla en la fila 0: {titulo!r}")
    return coincidencia.group(1).strip().capitalize()


def _extraer_campos(hoja: xlrd.sheet.Sheet, tabla_id: str) -> list[dict[str, Any]]:
    campos = []
    for fila in range(hoja.nrows):
        primera = hoja.cell_value(fila, 0)
        if not _es_fila_de_campo(primera):
            continue
        numero = int(primera)
        campos.append(
            {
                "numero": numero,
                "nombre": str(hoja.cell_value(fila, 1)).strip(),
                "obligatorio": _obligatorio_de_campo(hoja.cell_value(fila, 4)),
                "longitud": int(hoja.cell_value(fila, 5)),
                "decimales": _decimales_de_celda(
                    hoja.cell_value(fila, 6), f"{tabla_id} campo {numero}"
                ),
                "posicion_inicial": int(hoja.cell_value(fila, 7)),
                "descripcion": str(hoja.cell_value(fila, 2)).strip(),
                "criterios_texto": str(hoja.cell_value(fila, 3)).strip(),
            }
        )
    return campos


def _verificar_invariante_posiciones(tabla_id: str, campos: list[dict[str, Any]]) -> int:
    """Verifica numeracion consecutiva y que cada posicion_inicial encaje
    exactamente al final del campo anterior. Devuelve la longitud total."""

    campos_ordenados = sorted(campos, key=lambda c: c["numero"])
    numeros_reales = [c["numero"] for c in campos_ordenados]
    numeros_esperados = list(range(1, len(campos_ordenados) + 1))
    if numeros_reales != numeros_esperados:
        raise ValueError(f"{tabla_id}: numeracion de campos no consecutiva: {numeros_reales}")

    posicion_esperada = 1
    for campo in campos_ordenados:
        if campo["posicion_inicial"] != posicion_esperada:
            raise ValueError(
                f"{tabla_id} campo {campo['numero']}: posicion_inicial="
                f"{campo['posicion_inicial']}, se esperaba {posicion_esperada} "
                "(fin del campo anterior + 1)."
            )
        posicion_esperada += campo["longitud"]
    return posicion_esperada - 1


def _leer_obligatoriedad_por_tabla(libro_anexo3: xlrd.book.Book) -> dict[int, tuple[bool, bool]]:
    """{numero_tabla: (obligatoria, condicional)}, desde la tabla de
    consistencia de la hoja Estandares del Anexo 3 (columna 'Obligatorio
    por cada documento facturador'): 'Si' -> obligatoria; 'No(*)' ->
    condicional (obligatoria solo si el procedimiento/servicio se brindo);
    'No' -> opcional."""

    hoja = libro_anexo3.sheet_by_name("Estándares")
    resultado: dict[int, tuple[bool, bool]] = {}
    for fila in range(hoja.nrows):
        etiqueta = str(hoja.cell_value(fila, 0)).strip()
        coincidencia = _PATRON_ETIQUETA_TABLA.match(etiqueta)
        if not coincidencia:
            continue
        numero = int(coincidencia.group(1))
        valor = str(hoja.cell_value(fila, 1)).strip().upper()
        if valor == "SI":
            resultado[numero] = (True, False)
        elif valor.startswith("NO("):
            resultado[numero] = (False, True)
        elif valor == "NO":
            resultado[numero] = (False, False)
        else:
            raise ValueError(f"Obligatoriedad de tabla {numero} no reconocida: {valor!r}")

    faltantes = set(range(1, 9)) - set(resultado)
    if faltantes:
        raise ValueError(f"No se hallo la obligatoriedad de las tablas: {sorted(faltantes)}")
    return resultado


def main() -> None:
    for archivo in (ARCHIVO_ANEXO1, ARCHIVO_ANEXO3):
        if not archivo.exists():
            sys.exit(f"No se encontro el archivo fuente: {archivo}")

    libro1 = xlrd.open_workbook(str(ARCHIVO_ANEXO1))
    libro3 = xlrd.open_workbook(str(ARCHIVO_ANEXO3))
    obligatoriedad_por_tabla = _leer_obligatoriedad_por_tabla(libro3)

    tablas_salida = []
    total_campos = 0
    for tabla_id, nombre_hoja, prefijo, longitud_esperada in TABLAS_ANEXO1:
        hoja = libro1.sheet_by_name(nombre_hoja)
        campos = _extraer_campos(hoja, tabla_id)
        longitud_calculada = _verificar_invariante_posiciones(tabla_id, campos)
        if longitud_calculada != longitud_esperada:
            raise ValueError(
                f"{tabla_id}: longitud de registro calculada {longitud_calculada} "
                f"distinta de la esperada {longitud_esperada}."
            )
        obligatoria, condicional = obligatoriedad_por_tabla[int(tabla_id[1:])]

        tablas_salida.append(
            {
                "id": tabla_id,
                "nombre": _nombre_de_tabla(hoja),
                "prefijo": prefijo,
                "obligatoria": obligatoria,
                "condicional": condicional,
                "longitud_registro": longitud_calculada,
                "campos": campos,
            }
        )
        total_campos += len(campos)

    if total_campos != 218:
        raise ValueError(f"Total de campos extraidos: {total_campos}. Se esperaban 218.")

    esquema = {
        "version": "2025-10",
        "origen": ARCHIVO_ANEXO1.name,
        "huella_sha256": hashlib.sha256(ARCHIVO_ANEXO1.read_bytes()).hexdigest(),
        "tablas": tablas_salida,
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8") as archivo_salida:
        yaml.safe_dump(esquema, archivo_salida, allow_unicode=True, sort_keys=False, width=100)

    print(f"Esquema generado: {SALIDA} ({total_campos} campos, 8 tablas).")


if __name__ == "__main__":
    main()
