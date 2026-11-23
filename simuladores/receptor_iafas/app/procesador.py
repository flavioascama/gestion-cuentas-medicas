"""Procesador simple del lote recibido (Seccion 9.2, Seccion 9.3).

Descifra el .S01 con la contrasena de su IAFAS (Seccion 9.3: "Descifra el
.S01 con la contrasena de su IAFAS desde claves_iafas.json antes de
procesarlo. Un .S01 sin cifrar o con contrasena errónea se rechaza con
motivo explicito"). Despues de descifrar, verifica en este orden: el
nombre cumple el patron normado, contiene los archivos esperados (T1, T2,
T3) y cada linea de cada archivo tiene la longitud declarada por su
prefijo. Marca el lote ACEPTADO o RECHAZADO con un motivo textual.

Este procesador NO es el validador oficial de SUSALUD (Seccion 9.2, ultima
linea): no relee el contenido de los campos, no aplica los 458 criterios
del Anexo 1 ni las formulas de consistencia entre tablas -- eso ya lo hizo
el backend antes de remitir (Seccion 7). Aqui solo se verifica que el
archivo que llego sea, a nivel de transporte, el archivo que se declaro
que era.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path

import pyzipper

from app.longitudes_registro import LONGITUDES_REGISTRO
from app.nombrado import PATRON_NOMBRE_S01, nombre_archivo_txt_esperado

_PREFIJOS_ESPERADOS = ("dfac", "date", "dser")


@dataclass(frozen=True, slots=True)
class ResultadoProcesamiento:
    estado: str  # 'ACEPTADO' | 'RECHAZADO'
    motivo: str | None
    numero_lote: str | None = None
    codigo_iafas: str | None = None
    codigo_ipress: str | None = None
    # Comprobantes del lote aceptado (serie+numero, monto total facturado),
    # que pasan a la auditoria de la IAFAS (app/auditoria.py).
    documentos: tuple[tuple[str, Decimal], ...] = ()


# Tabla 1 del Anexo 1 (dfac): campo 8, numero del documento de pago
# (posicion 48, 12 caracteres), y campo 24, monto total facturado
# (posicion 188, 12 caracteres con dos decimales).
_T1_DOCUMENTO = slice(47, 59)
_T1_MONTO_TOTAL = slice(187, 199)
# Campos 25 y 27: tipo de nota (C credito, D debito, N ninguna) y su monto.
_T1_TIPO_NOTA = slice(199, 200)
_T1_MONTO_NOTA = slice(212, 224)
_T1_BASE_IMPONIBLE = slice(163, 175)
_T1_IGV = slice(175, 187)


def _monto_a_auditar(linea: str) -> Decimal:
    """Lo que la IAFAS reconoce del comprobante: su total menos la nota de
    credito, o mas la de debito. La nota viene sin IGV: se le suma el IGV
    con la tasa del propio comprobante (campos 22 y 23)."""
    monto = Decimal(linea[_T1_MONTO_TOTAL].strip())
    tipo_nota = linea[_T1_TIPO_NOTA]
    if tipo_nota not in ("C", "D"):
        return monto
    base = Decimal(linea[_T1_BASE_IMPONIBLE].strip() or "0")
    igv = Decimal(linea[_T1_IGV].strip() or "0")
    tasa = igv / base if base else Decimal(0)
    nota = (Decimal(linea[_T1_MONTO_NOTA].strip()) * (1 + tasa)).quantize(Decimal("0.01"))
    return monto - nota if tipo_nota == "C" else monto + nota


def _aceptado(
    componentes: dict[str, str], documentos: tuple[tuple[str, Decimal], ...] = ()
) -> ResultadoProcesamiento:
    return ResultadoProcesamiento(
        estado="ACEPTADO",
        motivo=None,
        numero_lote=componentes["lote"],
        codigo_iafas=componentes["iafas"],
        codigo_ipress=componentes["ipress"],
        documentos=documentos,
    )


def _documentos_de(
    paquete: pyzipper.AESZipFile, componentes: dict[str, str]
) -> tuple[tuple[str, Decimal], ...]:
    contenido = paquete.read(nombre_archivo_txt_esperado("dfac", componentes))
    documentos = []
    for linea in _lineas_de(contenido) or []:
        try:
            monto = _monto_a_auditar(linea)
        except InvalidOperation:
            continue  # linea sin monto legible: no se audita
        documentos.append((linea[_T1_DOCUMENTO].strip(), monto))
    return tuple(documentos)


def _rechazado(motivo: str) -> ResultadoProcesamiento:
    return ResultadoProcesamiento(estado="RECHAZADO", motivo=motivo)


def _lineas_de(contenido: bytes) -> list[str] | None:
    """None si el contenido no es ASCII decodificable (supuesto 1,
    docs/DECISIONES.md del backend: ASCII con transliteracion)."""

    try:
        texto = contenido.decode("ascii")
    except UnicodeDecodeError:
        return None
    if texto.endswith("\r\n"):
        texto = texto[: -len("\r\n")]
    return texto.split("\r\n") if texto else []


class _MotivoRechazoCifrado(Enum):
    NO_CIFRADO = "Archivo no cifrado: se esperaba un archivo cifrado con AES."
    CONTRASENA_INVALIDA = "Contraseña de descifrado inválida."


def _descifrar(
    ruta_zip: Path, contrasena: str | None
) -> tuple[pyzipper.AESZipFile | None, _MotivoRechazoCifrado | None]:
    """(None, motivo) si el archivo no esta cifrado o la contrasena es
    incorrecta; en ambos casos, RECHAZADO con un motivo explicito
    (Seccion 9.3)."""

    paquete = pyzipper.AESZipFile(ruta_zip)
    if any(not (info.flag_bits & 0x1) for info in paquete.infolist()):
        paquete.close()
        return None, _MotivoRechazoCifrado.NO_CIFRADO
    if contrasena is None:
        paquete.close()
        return None, _MotivoRechazoCifrado.CONTRASENA_INVALIDA
    paquete.setpassword(contrasena.encode("utf-8"))
    try:
        paquete.testzip()
    except RuntimeError:
        paquete.close()
        return None, _MotivoRechazoCifrado.CONTRASENA_INVALIDA
    return paquete, None


def _verificar_contenido(
    paquete: pyzipper.AESZipFile, componentes: dict[str, str]
) -> ResultadoProcesamiento | None:
    """None si el contenido interno es correcto; en ese caso, quien llama
    marca el lote ACEPTADO."""

    nombres_esperados = {
        prefijo: nombre_archivo_txt_esperado(prefijo, componentes)
        for prefijo in _PREFIJOS_ESPERADOS
    }
    faltantes = [n for n in nombres_esperados.values() if n not in paquete.namelist()]
    if faltantes:
        return _rechazado(f"Faltan archivos esperados dentro del ZIP: {faltantes}")

    for prefijo, nombre_interno in nombres_esperados.items():
        contenido = paquete.read(nombre_interno)
        lineas = _lineas_de(contenido)
        if lineas is None:
            return _rechazado(f"{nombre_interno}: contenido no es ASCII valido.")
        longitud_esperada = LONGITUDES_REGISTRO[prefijo]
        for numero_linea, linea in enumerate(lineas, start=1):
            if len(linea) != longitud_esperada:
                return _rechazado(
                    f"{nombre_interno}, linea {numero_linea}: longitud {len(linea)}, "
                    f"se esperaba {longitud_esperada} (prefijo {prefijo!r})."
                )
    return None


def procesar_lote(ruta_zip: Path, claves_iafas: dict[str, str]) -> ResultadoProcesamiento:
    coincidencia = PATRON_NOMBRE_S01.match(ruta_zip.name)
    if coincidencia is None:
        return _rechazado(f"El nombre del archivo no cumple el patron normado: {ruta_zip.name!r}")
    componentes = coincidencia.groupdict()

    try:
        contrasena = claves_iafas.get(componentes["iafas"])
        paquete, motivo = _descifrar(ruta_zip, contrasena)
        if paquete is None:
            assert motivo is not None
            return _rechazado(motivo.value)
        try:
            resultado = _verificar_contenido(paquete, componentes)
            documentos = _documentos_de(paquete, componentes) if resultado is None else ()
        finally:
            paquete.close()
        if resultado is not None:
            return resultado
    except pyzipper.BadZipFile:
        return _rechazado("El archivo no es un ZIP valido.")

    return _aceptado(componentes, documentos)
