"""Nombrado de archivos TEDEF (Seccion 2.2, hoja Estandares del Anexo 3).

Patrones literales del anexo:
    <prefijo>_<ruc_proveedor>_<Codigo IPRESS>_<Codigo IAFAS>_<lote>_<Periodo>_<fecha>.txt
    937_<ruc_proveedor>_<Codigo IPRESS>_<Codigo IAFAS>_<lote>_<Periodo>_<fecha>.S01

El '937' es el codigo de transaccion SUSALUD para este efecto (el propio
anexo lo etiqueta como '<EFS>' en el patron abstracto, pero su valor es
literalmente 937 en el ejemplo dado). RUC 11 caracteres, Codigo IPRESS 8,
Codigo IAFAS 5, lote 7, periodo 6 (AAAAMM, Decision de la Fase 1 punto 5),
fecha 8 (AAAAMMDD).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_CODIGO_TRANSACCION_SUSALUD = "937"

# Prefijo de nombre de archivo por tabla activa (hoja Estandares del
# Anexo 3), en el mismo orden que `tablas_activas.yaml`. "dfar" (T4,
# Fase 17) verificado contra el propio Anexo 3 en
# extraer_esquema_tedef.py (Fase 3). Reutilizado por generar_lote.py (al
# escribir) y por repositorio_validacion_oficial_sql.py (Fase 16, al
# recomputar el nombre esperado para localizar el archivo ya escrito).
PREFIJO_ARCHIVO_POR_TABLA = {"T1": "dfac", "T2": "date", "T3": "dser", "T4": "dfar"}


@dataclass(frozen=True, slots=True)
class IdentidadTrama:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): los seis
    datos que identifican un lote para nombrar cualquiera de sus archivos
    (`.txt` o `.S01`), sin exceder el limite de 5 parametros por funcion
    (Seccion 3)."""

    ruc: str
    codigo_ipress: str
    codigo_iafas: str
    numero_lote: str
    periodo: str
    fecha: date


# Deriva del ejemplo literal del Anexo 3:
# 937_20100121809_00140456_20002_1234567_201606_20130605.S01
PATRON_NOMBRE_TXT = re.compile(
    r"^(?P<prefijo>dfac|date|dser|dfar|dden|dpre|ddia|dprv)_"
    r"(?P<ruc>\d{11})_(?P<ipress>\d{8})_(?P<iafas>\d{5})_"
    r"(?P<lote>\d{7})_(?P<periodo>\d{6})_(?P<fecha>\d{8})\.txt$"
)
PATRON_NOMBRE_S01 = re.compile(
    r"^937_(?P<ruc>\d{11})_(?P<ipress>\d{8})_(?P<iafas>\d{5})_"
    r"(?P<lote>\d{7})_(?P<periodo>\d{6})_(?P<fecha>\d{8})\.S01$"
)


class ErrorNombreTedef(Exception):
    pass


def _validar_componentes(ruc: str, codigo_ipress: str, codigo_iafas: str, numero_lote: str) -> None:
    if len(ruc) != 11 or not ruc.isdigit():
        raise ErrorNombreTedef(f"RUC invalido para nombrar el archivo: {ruc!r}")
    if len(codigo_ipress) != 8:
        raise ErrorNombreTedef(f"Codigo IPRESS invalido para nombrar el archivo: {codigo_ipress!r}")
    if len(codigo_iafas) != 5 or not codigo_iafas.isdigit():
        raise ErrorNombreTedef(f"Codigo IAFAS invalido para nombrar el archivo: {codigo_iafas!r}")
    if len(numero_lote) != 7 or not numero_lote.isdigit():
        raise ErrorNombreTedef(f"Numero de lote invalido para nombrar el archivo: {numero_lote!r}")


def nombre_archivo_txt(prefijo: str, identidad: IdentidadTrama) -> str:
    _validar_componentes(
        identidad.ruc, identidad.codigo_ipress, identidad.codigo_iafas, identidad.numero_lote
    )
    nombre = (
        f"{prefijo}_{identidad.ruc}_{identidad.codigo_ipress}_{identidad.codigo_iafas}_"
        f"{identidad.numero_lote}_{identidad.periodo}_{identidad.fecha:%Y%m%d}.txt"
    )
    if not PATRON_NOMBRE_TXT.match(nombre):
        raise ErrorNombreTedef(f"Nombre de archivo generado no calza con el patron: {nombre!r}")
    return nombre


def nombre_archivo_s01(identidad: IdentidadTrama) -> str:
    _validar_componentes(
        identidad.ruc, identidad.codigo_ipress, identidad.codigo_iafas, identidad.numero_lote
    )
    nombre = (
        f"{_CODIGO_TRANSACCION_SUSALUD}_{identidad.ruc}_{identidad.codigo_ipress}_"
        f"{identidad.codigo_iafas}_{identidad.numero_lote}_{identidad.periodo}_"
        f"{identidad.fecha:%Y%m%d}.S01"
    )
    if not PATRON_NOMBRE_S01.match(nombre):
        raise ErrorNombreTedef(f"Nombre de archivo generado no calza con el patron: {nombre!r}")
    return nombre
