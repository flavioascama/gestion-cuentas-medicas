"""Exporta el esquema OpenAPI de la API (Seccion 11 del plan v3, Fase 18)
a `sistema/frontend/src/api/esquema_openapi.json`, para generar ahi los
tipos del futuro cliente del frontend.

Uso (desde sistema/backend/):
    uv run python herramientas/exportar_openapi.py
"""

from __future__ import annotations

import json

from app.compartido.rutas import raiz_frontend

_RUTA_SALIDA = raiz_frontend() / "src" / "api" / "esquema_openapi.json"


def main() -> None:
    from app.api.main import app

    esquema = app.openapi()
    _RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    _RUTA_SALIDA.write_text(
        json.dumps(esquema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Esquema OpenAPI exportado a {_RUTA_SALIDA} ({len(esquema['paths'])} rutas).")


if __name__ == "__main__":
    main()
