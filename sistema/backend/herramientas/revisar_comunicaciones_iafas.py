"""Encola la revision del portal y del correo de la IAFAS (comunicaciones
de conformidad, glosa, liquidacion y pago). La agenda el temporizador
cada TEMPORIZADOR_INTERVALO_COMUNICACIONES_MINUTOS; no encola otra si la
anterior aun no termina.

Uso (desde sistema/backend/):
    uv run python -m herramientas.revisar_comunicaciones_iafas
"""

from __future__ import annotations

import asyncio

from app.dominio.comunicaciones.casos_uso import SolicitarRevisionComunicaciones
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)
from app.infraestructura.reloj import RelojSistema


async def main() -> None:
    async with FabricaSesiones() as sesion:
        trabajo_id = await SolicitarRevisionComunicaciones(
            RepositorioComunicacionesSql(sesion), RepositorioTrabajosSql(sesion), RelojSistema()
        ).ejecutar("temporizador")
    print(f"revision de comunicaciones IAFAS: trabajo {trabajo_id}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
