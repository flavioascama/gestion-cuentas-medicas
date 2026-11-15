"""Solicita la carga de un lote GENERADO en el validador TEDEF Web
(Seccion 8.3: "el usuario solicita la carga del lote en el validador").
Sin interfaz todavia (Fase 18), este script hace las veces de ese boton
-- el trabajador (sistema/automatizacion/, docker compose up trabajador)
lo procesa en segundos si ya hay una sesion asistida ACTIVA para TEDEF
Web (ver herramientas/solicitar_sesion_plataforma_ejemplo.py).

Uso (desde sistema/backend/):
    uv run python herramientas/solicitar_carga_validador_ejemplo.py <lote_id>
"""

from __future__ import annotations

import asyncio
import sys

from app.dominio.integracion.casos_uso_validacion import SolicitarCargaEnValidador
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    RepositorioValidacionOficialSql,
)
from app.infraestructura.reloj import RelojSistema


async def main(lote_id: int) -> None:
    async with FabricaSesiones() as sesion:
        caso_uso = SolicitarCargaEnValidador(
            repositorio=RepositorioValidacionOficialSql(sesion),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            reloj=RelojSistema(),
        )
        trabajo_id = await caso_uso.ejecutar(lote_id=lote_id, actor="verificacion_manual")

    print(f"trabajo_id: {trabajo_id}")
    print("El trabajador lo procesa en segundos si hay sesion ACTIVA para tedef_web.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: solicitar_carga_validador_ejemplo.py <lote_id>")
    asyncio.run(main(int(sys.argv[1])))
