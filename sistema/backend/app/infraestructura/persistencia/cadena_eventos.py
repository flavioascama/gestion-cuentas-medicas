"""Encadenamiento del almacen de eventos con valor resumen con clave
(HMAC-SHA256, Seccion 6.2.2, RNF-18, AD-11): cada evento se firma con sus
propios campos y con el `hash_evento` del evento anterior del mismo
agregado, con una clave que reside fuera de la base de datos
(`Configuracion.clave_hmac_eventos`). Lo usan tanto el adaptador que
inserta eventos (`registro_eventos_sql.py`) como las herramientas de
anclaje y verificacion diaria (Seccion 6.2.2: "el ultimo valor se ancla
diariamente fuera de la base y un procedimiento diario verifica la cadena
completa").

GENESIS es el valor previo de un agregado que todavia no tiene eventos
(el primero de cada cuenta, lote o sesion): un valor fijo, publico, que no
depende de ningun secreto -- lo que protege la cadena es la clave, no el
valor inicial.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

GENESIS = "0" * 64


@dataclass(frozen=True, slots=True)
class DatosEventoParaHash:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): los
    campos del evento sobre los que se calcula su `hash_evento`, tal como
    los define la Tabla 68 de la tesis (todos menos el propio
    hash_evento, que es lo que esta funcion produce)."""

    tipo_agregado: str
    agregado_id: int
    version: int
    tipo_evento: str
    actor: str
    estado_previo: str | None
    estado_nuevo: str | None
    ocurrido_en: datetime


def _instante_canonico(instante: datetime) -> str:
    """Representacion estable de `ocurrido_en`, independiente de como cada
    dialecto (SQLite, PostgreSQL) devuelva el campo de zona horaria tras
    una ida y vuelta a la base: sin esto, dos lecturas del mismo instante
    podrian formatearse distinto con `str()` y producir un hash distinto
    para el mismo evento."""

    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC).isoformat()


def calcular_hash_evento(clave: bytes, hash_anterior: str, datos: DatosEventoParaHash) -> str:
    base = "|".join(
        str(valor) if not isinstance(valor, datetime) else _instante_canonico(valor)
        for valor in (
            datos.tipo_agregado,
            datos.agregado_id,
            datos.version,
            datos.tipo_evento,
            datos.actor,
            datos.estado_previo,
            datos.estado_nuevo,
            datos.ocurrido_en,
        )
    )
    mensaje = f"{hash_anterior}|{base}".encode()
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def calcular_hash_evento_de_fila(clave: bytes, hash_anterior: str, fila: dict[str, Any]) -> str:
    """Misma funcion, a partir de una fila leida de la base (dict con esas
    mismas claves) -- lo que usan las herramientas de verificacion, que
    recorren la tabla en vez de construir cada evento desde el dominio."""

    return calcular_hash_evento(
        clave,
        hash_anterior,
        DatosEventoParaHash(
            tipo_agregado=fila["tipo_agregado"],
            agregado_id=fila["agregado_id"],
            version=fila["version"],
            tipo_evento=fila["tipo_evento"],
            actor=fila["actor"],
            estado_previo=fila["estado_previo"],
            estado_nuevo=fila["estado_nuevo"],
            ocurrido_en=fila["ocurrido_en"],
        ),
    )
