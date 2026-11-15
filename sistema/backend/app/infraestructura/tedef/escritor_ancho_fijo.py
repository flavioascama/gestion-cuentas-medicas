"""Escritor de ancho fijo (Seccion 7.3, Seccion 7.6).

Formatea valores Python a los patrones de texto de ancho fijo del Anexo 1
y concatena una fila completa, verificando su longitud contra el esquema
(Seccion 7.1). Codificacion ASCII con transliteracion y fin de linea
'\\r\\n' (docs/DECISIONES.md, supuestos 1 y 2).
"""

from __future__ import annotations

import unicodedata
from datetime import date, time
from decimal import Decimal

from app.dominio.integracion.esquema import CampoEsquema, TablaEsquema


class ErrorEscrituraTedef(Exception):
    """El escritor no pudo producir una linea conforme al esquema."""


def formatear_monto(valor: Decimal | None, campo: CampoEsquema) -> str:
    """'999999999.99', alineado a la derecha. Por defecto '0.00'. Nunca
    negativo (Seccion 7.3): un monto negativo es un error de quien llama,
    no algo que el escritor deba silenciar."""

    monto = valor if valor is not None else Decimal("0.00")
    if monto < 0:
        raise ErrorEscrituraTedef(
            f"Monto negativo no permitido en el campo {campo.numero} ({campo.nombre}): {monto}"
        )
    texto = f"{monto:.2f}"
    if len(texto) > campo.longitud:
        raise ErrorEscrituraTedef(
            f"Monto demasiado largo para el campo {campo.numero} ({campo.nombre}): {texto!r}"
        )
    return texto.rjust(campo.longitud)


def formatear_fecha(valor: date | None, campo: CampoEsquema) -> str:
    """AAAAMMDD, 8 caracteres. En blanco si no hay valor (campo opcional)."""

    if valor is None:
        return " " * campo.longitud
    return valor.strftime("%Y%m%d")


def formatear_hora(valor: time | None, campo: CampoEsquema) -> str:
    """HHMMSS, 6 caracteres. En blanco si no hay valor (campo opcional)."""

    if valor is None:
        return " " * campo.longitud
    return valor.strftime("%H%M%S")


def formatear_numerico_con_ceros(valor: int | str | None, campo: CampoEsquema) -> str:
    """Alineado a la derecha con ceros a la izquierda (Seccion 7.3)."""

    if valor is None:
        return " " * campo.longitud
    texto = str(valor)
    if not texto.isdigit() or len(texto) > campo.longitud:
        raise ErrorEscrituraTedef(
            f"Valor numerico invalido para el campo {campo.numero} ({campo.nombre}): {texto!r}"
        )
    return texto.rjust(campo.longitud, "0")


def formatear_alfanumerico(valor: str | None, campo: CampoEsquema, derecha: bool = False) -> str:
    """Alineado a la izquierda con espacios a la derecha por defecto
    (Seccion 7.3, supuesto documentado). `derecha=True` para los pocos
    campos alfanumericos cuyo propio criterio exige alinear a la derecha
    (por ejemplo T2 campos 8 y 10, ver el diccionario de mapeo)."""

    if not valor:
        return " " * campo.longitud
    if len(valor) > campo.longitud:
        raise ErrorEscrituraTedef(
            f"Valor demasiado largo para el campo {campo.numero} ({campo.nombre}): {valor!r}"
        )
    return valor.rjust(campo.longitud) if derecha else valor.ljust(campo.longitud)


def escribir_registro(tabla: TablaEsquema, valores_formateados: dict[int, str]) -> str:
    """Concatena los valores YA formateados (por las funciones de arriba)
    en el orden de los campos de la tabla. Aborta si falta un campo o si
    la longitud final no coincide con la del esquema (Seccion 7.1)."""

    partes = []
    for campo in sorted(tabla.campos, key=lambda c: c.numero):
        valor = valores_formateados.get(campo.numero)
        if valor is None:
            raise ErrorEscrituraTedef(f"Falta el campo {campo.numero} de {tabla.id}.")
        if len(valor) != campo.longitud:
            raise ErrorEscrituraTedef(
                f"{tabla.id} campo {campo.numero}: longitud {len(valor)}, "
                f"se esperaba {campo.longitud}."
            )
        partes.append(valor)

    linea = "".join(partes)
    if len(linea) != tabla.longitud_registro:
        raise ErrorEscrituraTedef(
            f"{tabla.id}: longitud de linea {len(linea)}, se esperaba {tabla.longitud_registro}."
        )
    return linea


def transliterar_ascii(texto: str) -> str:
    """Decision documentada (docs/DECISIONES.md, supuesto 1): ASCII con
    transliteracion. Un caracter que no tiene equivalente ASCII se
    descarta, nunca se sustituye por un valor inventado."""

    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("ascii", "ignore").decode("ascii")


def ensamblar_archivo(lineas: list[str]) -> bytes:
    """Une las lineas con '\\r\\n' (supuesto 1) y transliteral a ASCII."""

    contenido = "\r\n".join(transliterar_ascii(linea) for linea in lineas)
    if lineas:
        contenido += "\r\n"
    return contenido.encode("ascii")
