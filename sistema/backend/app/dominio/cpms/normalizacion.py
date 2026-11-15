"""Normalizacion de texto libre para el motor de sugerencia CPMS (Seccion
8.2, punto 2): 'minusculas, sin tildes, sin puntuacion, espacios
colapsados'. Puro stdlib -- sin dependencia de scikit-learn ni de
SQLAlchemy -- porque tanto el motor (infraestructura) como el caso de uso
de coincidencia exacta (dominio) necesitan la MISMA normalizacion sobre la
MISMA entrada."""

from __future__ import annotations

import re
import unicodedata

_PUNTUACION_Y_SIMBOLOS = re.compile(r"[^\w\s]", re.UNICODE)
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    texto = _PUNTUACION_Y_SIMBOLOS.sub(" ", texto)
    texto = _ESPACIOS.sub(" ", texto).strip()
    return texto


def es_codigo_candidato(texto_normalizado: str) -> bool:
    """Seccion 8.2, punto 3: 'coincidencia exacta por codigo si la entrada
    es un codigo existente'. Los codigos del catalogo (Fase 4) son
    numericos; esto solo decide si vale la pena consultar el repositorio
    por coincidencia exacta, no valida el codigo en si."""

    return texto_normalizado.isdigit()
