"""Solicita una sesion asistida (Seccion 8.4, punto 1: "el usuario pulsa
'Iniciar sesion' para una plataforma"). Sin interfaz todavia (Fase 18),
este script hace las veces de ese boton.

Uso (desde sistema/backend/):
    uv run python herramientas/solicitar_sesion_plataforma_ejemplo.py [acredita_salud|tedef_web]
"""

from __future__ import annotations

import asyncio
import sys

from app.dominio.plataformas.casos_uso import SolicitarSesionPlataforma
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)
from app.infraestructura.reloj import RelojSistema


async def main(plataforma: str) -> None:
    async with FabricaSesiones() as sesion:
        caso_uso = SolicitarSesionPlataforma(
            repositorio=RepositorioSesionPlataformaSql(sesion),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            reloj=RelojSistema(),
        )
        sesion_id = await caso_uso.ejecutar(
            plataforma=plataforma, solicitada_por="verificacion_manual"
        )

    print(f"sesion_id: {sesion_id}")
    print(
        "El trabajador (sistema/automatizacion/, docker compose up trabajador) va a "
        "abrir la pagina de ingreso y publicar la imagen del CAPTCHA en unos segundos. "
        "Consulte sesion_plataforma para verla, y responda con "
        "herramientas/responder_captcha_sesion_ejemplo.py."
    )


if __name__ == "__main__":
    plataforma_arg = sys.argv[1] if len(sys.argv) > 1 else "acredita_salud"
    asyncio.run(main(plataforma_arg))
