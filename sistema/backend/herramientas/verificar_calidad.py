"""Verifica los limites de GUIA_ESTILO_CODIGO.md, Seccion 5: ejecuta
`ruff check`, `ruff format --check` y `mypy`, y ademas los dos limites que
esas herramientas no cubren en Python (lineas por funcion, lineas por
archivo -- Seccion 3). Termina con codigo distinto de cero si algo falla,
para usarse como un unico paso de verificacion por fase.

Alcance: solo sistema/backend/ (app/, herramientas/, pruebas/). El
trabajador de sistema/automatizacion/ vive en su propio contenedor, con su
propio entorno `uv`, sin acceso a este arbol dentro de Docker (ver
docker-compose.yml); sus propios `ruff`/`mypy`/`pytest` se corren aparte,
como documenta el README.

Uso (desde sistema/backend/):
    uv run python herramientas/verificar_calidad.py
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIOS_PYTHON = ("app", "herramientas", "pruebas")

LIMITE_LINEAS_FUNCION = 50
LIMITE_LINEAS_ARCHIVO = 400


def _archivos_python() -> list[Path]:
    archivos: list[Path] = []
    for directorio in DIRECTORIOS_PYTHON:
        archivos.extend((RAIZ / directorio).rglob("*.py"))
    return sorted(archivos)


def _verificar_lineas_por_archivo(archivos: list[Path]) -> list[str]:
    errores = []
    for archivo in archivos:
        total = len(archivo.read_text(encoding="utf-8").splitlines())
        if total > LIMITE_LINEAS_ARCHIVO:
            ruta = archivo.relative_to(RAIZ)
            errores.append(f"{ruta}: {total} lineas (limite {LIMITE_LINEAS_ARCHIVO})")
    return errores


def _verificar_lineas_por_funcion(archivos: list[Path]) -> list[str]:
    errores = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if nodo.end_lineno is None:
                continue
            total = nodo.end_lineno - nodo.lineno + 1
            if total > LIMITE_LINEAS_FUNCION:
                ruta = archivo.relative_to(RAIZ)
                errores.append(
                    f"{ruta}:{nodo.lineno}: {nodo.name}() tiene {total} lineas "
                    f"(limite {LIMITE_LINEAS_FUNCION})"
                )
    return errores


def _ejecutar(descripcion: str, comando: list[str]) -> bool:
    print(f"--- {descripcion} ---")
    resultado = subprocess.run(comando, cwd=RAIZ)
    return resultado.returncode == 0


def main() -> int:
    archivos = _archivos_python()
    errores_lineas = _verificar_lineas_por_archivo(archivos) + _verificar_lineas_por_funcion(
        archivos
    )
    if errores_lineas:
        print("--- limites de lineas (Seccion 3 de GUIA_ESTILO_CODIGO.md) ---")
        for error in errores_lineas:
            print(f"ERROR {error}")

    ok_ruff_check = _ejecutar("ruff check", ["uv", "run", "ruff", "check", "."])
    ok_ruff_format = _ejecutar(
        "ruff format --check", ["uv", "run", "ruff", "format", "--check", "."]
    )
    ok_mypy = _ejecutar("mypy", ["uv", "run", "mypy", "app"])

    ok = not errores_lineas and ok_ruff_check and ok_ruff_format and ok_mypy
    print("TODO EN VERDE" if ok else "FALLO LA VERIFICACION DE CALIDAD")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
