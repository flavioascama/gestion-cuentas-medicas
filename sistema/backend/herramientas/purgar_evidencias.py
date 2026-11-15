"""Retencion de las evidencias del robot (C-12): borra las carpetas de
evidencia de acreditacion con mas de RETENCION_EVIDENCIAS_DIAS dias. Lo
corre el temporizador una vez al dia.

Uso (desde sistema/backend/):
    uv run python -m herramientas.purgar_evidencias
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.compartido.configuracion import obtener_configuracion
from app.compartido.rutas import raiz_reportes


def purgar(raiz: Path, retencion_dias: int, ahora: datetime) -> list[str]:
    limite = (ahora - timedelta(days=retencion_dias)).timestamp()
    carpeta = raiz / "evidencia_acreditacion"
    if not carpeta.exists():
        return []
    vencidas = [c for c in carpeta.iterdir() if c.is_dir() and c.stat().st_mtime < limite]
    for vencida in vencidas:
        shutil.rmtree(vencida)
    return sorted(c.name for c in vencidas)


async def main() -> None:
    retencion = obtener_configuracion().retencion_evidencias_dias
    borradas = purgar(raiz_reportes(), retencion, datetime.now(UTC))
    print(f"evidencias con mas de {retencion} dias borradas: {len(borradas)} {borradas}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
