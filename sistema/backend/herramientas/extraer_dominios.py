"""Propone candidatos de dominios enumerados (Seccion 7.4) a partir de la
columna 'Descripcion y formato' del esquema ya extraido (Fase 3).

Un dominio es una lista de pares codigo=etiqueta que aparece en la
descripcion de un campo, por ejemplo el campo 16 de T1:
    1 Soles
    2 Dolares

Este script SOLO propone: cada entrada nace con `confirmado: false`. La
Seccion 7.4 es explicita: "cada dominio requiere revision humana antes de
marcarse como confirmado. Un dominio no confirmado produce advertencia, no
rechazo." Ningun script debe marcar `confirmado: true` por si mismo.

Heuristica de deteccion: una linea de la descripcion que empieza con un
codigo corto (letras/digitos, sin espacios) seguido de '=', '.', ':' o un
guion, y luego una etiqueta. Los ejemplos reales del Anexo 1 usan las
cuatro formas ('1 = Soles', '01. Factura', '00: Profesional sin
colegiatura', 'C. Nota de Credito'). Una descripcion sin ninguna linea que
calce este patron no genera un dominio.

Uso (desde sistema/backend/):
    uv run python herramientas/extraer_dominios.py
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from app.compartido.rutas import RAIZ_BACKEND

ESQUEMA = RAIZ_BACKEND / "configuracion" / "esquema_tedef" / "esquema_2025_10.yaml"
SALIDA = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "dominios.yaml"

_PATRON_VALOR = re.compile(r"^\s*([A-Za-z0-9]{1,3})\s*[=.:]\s*(.+?)\s*$")


def _candidatos_de_descripcion(descripcion: str) -> list[dict[str, str]]:
    candidatos = []
    for linea in descripcion.splitlines():
        coincidencia = _PATRON_VALOR.match(linea)
        if coincidencia:
            codigo, etiqueta = coincidencia.groups()
            candidatos.append({"codigo": codigo, "etiqueta": etiqueta})
    return candidatos


def _construir_dominios(esquema: dict[str, Any]) -> list[dict[str, Any]]:
    dominios = []
    for tabla in esquema["tablas"]:
        for campo in tabla["campos"]:
            candidatos = _candidatos_de_descripcion(campo["descripcion"])
            # Se exige mas de un valor: una sola coincidencia suele ser un
            # formato ('AAAAMMDD') mal detectado, no un dominio real.
            if len(candidatos) < 2:
                continue
            dominios.append(
                {
                    "tabla": tabla["id"],
                    "campo": campo["numero"],
                    "nombre": campo["nombre"],
                    "confirmado": False,
                    "valores": candidatos,
                }
            )
    return dominios


def main() -> None:
    with ESQUEMA.open(encoding="utf-8") as archivo:
        esquema = yaml.safe_load(archivo)

    dominios = _construir_dominios(esquema)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8") as archivo_salida:
        archivo_salida.write(
            "# Dominios enumerados candidatos (Seccion 7.4). Generado por\n"
            "# herramientas/extraer_dominios.py: TODOS nacen con\n"
            "# 'confirmado: false'. Un dominio no confirmado produce\n"
            "# advertencia en el validador, nunca rechazo. Cambiar a\n"
            "# 'confirmado: true' es una decision humana, campo por campo,\n"
            "# tras comparar contra el Anexo 1 y, si corresponde, contra el\n"
            "# catalogo oficial de SUSALUD.\n"
        )
        yaml.safe_dump(dominios, archivo_salida, allow_unicode=True, sort_keys=False, width=100)

    confirmados = sum(1 for d in dominios if d["confirmado"])
    print(f"{len(dominios)} dominios candidatos escritos en {SALIDA} ({confirmados} confirmados).")


if __name__ == "__main__":
    main()
