"""Solicita el envio a SUSALUD de los lotes VALIDADO (o posteriores) de
un periodo (Seccion 8.3: "el usuario envia a SUSALUD los lotes del
periodo"). Sin interfaz todavia (Fase 18), este script hace las veces de
ese boton.

Uso (desde sistema/backend/):
    uv run python herramientas/solicitar_envio_susalud_ejemplo.py <periodo>
"""

from __future__ import annotations

import asyncio
import sys

from app.dominio.integracion.casos_uso_validacion import SolicitarEnvioSusalud
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    RepositorioValidacionOficialSql,
)
from app.infraestructura.reloj import RelojSistema


async def main(periodo: str) -> None:
    async with FabricaSesiones() as sesion:
        caso_uso = SolicitarEnvioSusalud(
            repositorio=RepositorioValidacionOficialSql(sesion),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            reloj=RelojSistema(),
        )
        trabajo_id = await caso_uso.ejecutar(periodo=periodo, actor="verificacion_manual")

    if trabajo_id is None:
        print(f"No hay lotes pendientes de envio a SUSALUD para el periodo {periodo!r}.")
        return
    print(f"trabajo_id: {trabajo_id}")
    print("El trabajador lo procesa en segundos si hay sesion ACTIVA para tedef_web.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: solicitar_envio_susalud_ejemplo.py <periodo>")
    asyncio.run(main(sys.argv[1]))
