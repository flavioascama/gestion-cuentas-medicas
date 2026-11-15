"""Huella de integridad de archivos (Regla 11 del plan v3): el backend
nunca produce ni abre el `.S01`, pero sí necesita verificar que el
archivo que remite es exactamente el que el validador le entregó. Antes
vivía en `infraestructura/tedef/compresion.py`, junto a la compresión
propia del `.S01`; esa compresión se fue al simulador TEDEF Web (Fase
13, ver `docs/MIGRACION_V2_A_V3.md`), pero esta funcion de proposito
general se conserva."""

from __future__ import annotations

import hashlib


def huella_sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()
