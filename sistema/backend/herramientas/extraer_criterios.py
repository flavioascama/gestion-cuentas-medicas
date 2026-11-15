"""Extrae el catalogo de criterios de consistencia del Anexo 1 (Seccion 7.4)
a `configuracion/reglas_tedef/criterios.csv`, una fila por criterio.

Lee el esquema YA EXTRAIDO (esquema_2025_10.yaml), no el .xls: ese YAML ya
conserva literalmente el texto de la columna "Criterios de consistencia"
por campo (Regla 0.1, el .xls no se lee dos veces con logica distinta).

El anexo numera casi todos los criterios como 'C1.' o 'C1:' seguidos de
texto, varios por campo. Un pequeno numero de campos (6 de 218, verificado
al escribir este script) no usa ese formato: presentan un solo criterio en
prosa libre o en lista con vinetas, sin numerar. Para esos campos se genera
un unico criterio sintetico 'C1' que conserva el texto integro tal como
aparece: no se inventa contenido, solo se le da un identificador a un
criterio que la fuente no numero. Ver docs/DECISIONES.md.

Las columnas 'implementada' y 'regla' quedan en 'no' y vacias: las llena la
Fase 6 (validador) a medida que cada criterio obtiene una estrategia.

Uso (desde sistema/backend/):
    uv run python herramientas/extraer_criterios.py
"""

from __future__ import annotations

import csv
import re
import sys

import yaml

from app.compartido.rutas import RAIZ_BACKEND

ESQUEMA = RAIZ_BACKEND / "configuracion" / "esquema_tedef" / "esquema_2025_10.yaml"
SALIDA = RAIZ_BACKEND / "configuracion" / "reglas_tedef" / "criterios.csv"

# Acepta 'C1.' y 'C1:' (ambos aparecen en el anexo). Ver docs/DECISIONES.md.
_PATRON_CRITERIO = re.compile(r"C(\d+)\s*[.:]\s*")

_ENCABEZADOS = [
    "tabla",
    "campo_numero",
    "campo_nombre",
    "criterio_id",
    "texto_literal",
    "implementada",
    "regla",
]


def _dividir_criterios(texto: str) -> list[tuple[str, str]]:
    """[(criterio_id, texto_literal), ...]. Si no hay marcador 'Cn', el
    texto completo es un unico criterio sintetico 'C1'."""

    coincidencias = list(_PATRON_CRITERIO.finditer(texto))
    if not coincidencias:
        return [("C1", texto.strip())]

    criterios = []
    for indice, coincidencia in enumerate(coincidencias):
        inicio = coincidencia.end()
        fin = coincidencias[indice + 1].start() if indice + 1 < len(coincidencias) else len(texto)
        criterios.append((f"C{coincidencia.group(1)}", texto[inicio:fin].strip()))
    return criterios


def main() -> None:
    if not ESQUEMA.exists():
        sys.exit(
            f"No se encontro {ESQUEMA}. Ejecute primero herramientas/extraer_esquema_tedef.py."
        )

    with ESQUEMA.open(encoding="utf-8") as archivo:
        esquema = yaml.safe_load(archivo)

    filas = []
    campos_sin_marcador = []
    for tabla in esquema["tablas"]:
        for campo in tabla["campos"]:
            criterios = _dividir_criterios(campo["criterios_texto"])
            if len(criterios) == 1 and not _PATRON_CRITERIO.search(campo["criterios_texto"]):
                campos_sin_marcador.append(f"{tabla['id']} campo {campo['numero']}")
            for criterio_id, texto_literal in criterios:
                filas.append(
                    {
                        "tabla": tabla["id"],
                        "campo_numero": campo["numero"],
                        "campo_nombre": campo["nombre"],
                        "criterio_id": criterio_id,
                        "texto_literal": texto_literal,
                        "implementada": "no",
                        "regla": "",
                    }
                )

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8", newline="") as archivo_salida:
        escritor = csv.DictWriter(archivo_salida, fieldnames=_ENCABEZADOS)
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"Criterios extraidos: {len(filas)} en {SALIDA}.")
    if campos_sin_marcador:
        print(
            f"{len(campos_sin_marcador)} campos sin numeracion 'Cn' en el anexo "
            f"(un solo criterio sintetico 'C1' cada uno): " + ", ".join(campos_sin_marcador)
        )


if __name__ == "__main__":
    main()
