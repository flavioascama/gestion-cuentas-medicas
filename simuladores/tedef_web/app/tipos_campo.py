"""Clasificador de tipo de campo a partir del texto de criterios del
Anexo 1 (Seccion 9.2: "formatos por tipo de campo"). Heuristica propia por
palabras clave, escrita desde cero (Regla 12: no reutiliza la
interpretacion del backend sobre el mismo texto)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import Enum

_PATRON_MONTO = re.compile(r"^-?\d+\.\d{2}$")
# "no debe estar en blanco" (y su variante con "estar" duplicado, tal
# cual aparece en el Anexo 1) es una reafirmacion de obligatoriedad, no
# una excepcion -- se excluye antes de buscar la palabra "blanco" sola.
_PATRON_NO_BLANCO = re.compile(r"no\s+(debe[a-z]*\s+)?est\w*\s+(estar\s+)?en\s+blanco")
# Los campos de monto de la Tabla 4 (Fase 17) no repiten la frase "valor
# numerico ... decimales" de las Tablas 1-3: su propio criterio dice
# solo "rango numerico del [0 al 9]", igual que un campo entero. La
# unica senal propia que los distingue en su texto es el valor por
# defecto "'0.00'" (dos decimales), asi que sirve como segunda condicion
# de MONTO ademas de la frase original (docs/DECISIONES.md, Fase 17).
_PATRON_DEFECTO_DECIMAL = re.compile(r"'0\.00'")


class TipoCampo(Enum):
    FECHA = "fecha"
    HORA = "hora"
    MONTO = "monto"
    NUMERICO = "numerico"
    ALFANUMERICO = "alfanumerico"


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def clasificar(criterios_texto: str) -> TipoCampo:
    # Sin acentos para que "valida"/"válida", "numerico"/"numérico", etc.
    # coincidan con la misma palabra clave sin enumerar cada variante.
    texto = _sin_acentos(criterios_texto.lower())
    if "fecha" in texto and "valid" in texto:
        return TipoCampo.FECHA
    if "hora" in texto and "valid" in texto:
        return TipoCampo.HORA
    if "valor num" in texto and "decimal" in texto:
        return TipoCampo.MONTO
    if _PATRON_DEFECTO_DECIMAL.search(texto) and (
        "rango num" in texto or "caracteres entre" in texto
    ):
        return TipoCampo.MONTO
    # Un campo cuyo propio criterio admite caracteres alfanumericos en
    # alguna parte (por ejemplo, la serie de un documento de pago
    # electronico), o cuyo rango numerico solo aplica "para el caso" de
    # un valor concreto de otro campo (por ejemplo, el numero de
    # documento de identidad solo es numerico "para el caso del DNI";
    # "para otros casos" acepta CE, pasaporte, etc.), no es puramente
    # numerico en general.
    es_numerico_condicionado = "otros casos" in texto or "para el caso" in texto
    if (
        ("rango num" in texto or "caracteres entre" in texto)
        and "alfanumeric" not in texto
        and not es_numerico_condicionado
    ):
        return TipoCampo.NUMERICO
    return TipoCampo.ALFANUMERICO


def formato_valido(tipo: TipoCampo, valor: str) -> bool:
    """Solo verifica el FORMATO del valor ya extraido (longitud correcta
    por construccion, al venir de una posicion fija). No reproduce
    formulas de consistencia entre campos: eso queda fuera del
    subconjunto simulado (Seccion 9.2)."""

    if tipo is TipoCampo.FECHA:
        return _fecha_valida(valor)
    if tipo is TipoCampo.HORA:
        return valor.isdigit()
    if tipo is TipoCampo.MONTO:
        return bool(_PATRON_MONTO.match(valor))
    if tipo is TipoCampo.NUMERICO:
        return valor.isdigit()
    return True


def obligatoriedad_es_condicional(criterios_texto: str) -> bool:
    """True cuando el propio criterio del Anexo 1 admite que el campo
    quede en blanco bajo alguna condicion (por ejemplo, "debera ir en
    blanco" o "de corresponder"), aunque la columna Obligatorio diga
    'SI'. Sin poder evaluar esa condicion (depende de otros campos de la
    misma linea, fuera del subconjunto simulado -- Seccion 9.2), la
    obligatoriedad general de la columna no es segura de aplicar."""

    texto = _sin_acentos(criterios_texto.lower())
    # Frase inequivoca de excepcion (manda dejar el campo en blanco bajo
    # una condicion): prevalece aunque el mismo criterio tambien
    # reafirme la obligatoriedad para otra condicion distinta (por
    # ejemplo, un campo obligatorio "para el caso del DNI" pero que
    # "debera ir en blanco" cuando el profesional responsable es '00').
    if "debera ir en blanco" in texto or "podra consignarse en blanco" in texto:
        return True
    if _PATRON_NO_BLANCO.search(texto):
        return False
    return "blanco" in texto or "de corresponder" in texto


def _fecha_valida(valor: str) -> bool:
    if len(valor) != 8 or not valor.isdigit():
        return False
    try:
        datetime.strptime(valor, "%Y%m%d")
    except ValueError:
        return False
    return True
