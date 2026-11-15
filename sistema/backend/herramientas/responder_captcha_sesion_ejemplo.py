"""Responde el CAPTCHA de una sesion asistida (Seccion 8.4, punto 3: "la
aplicacion web consulta el estado, muestra la imagen en un dialogo y el
usuario escribe el texto"). Sin interfaz todavia (Fase 18), este script
hace las veces de ese dialogo -- actua como el usuario humano, nunca como
el robot (Seccion 8.4: "la prueba actua como el usuario humano llamando a
la API del sistema"). El texto del CAPTCHA se lee de la ruta de
administracion del simulador (SIMULADOR_MODO_PRUEBA=true), no por
reconocimiento optico.

Uso (desde sistema/backend/):
    uv run python herramientas/responder_captcha_sesion_ejemplo.py <sesion_id> <respuesta>
"""

from __future__ import annotations

import asyncio
import sys

from app.dominio.plataformas.casos_uso import ResponderCaptcha
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)


async def main(sesion_id: int, respuesta: str) -> None:
    async with FabricaSesiones() as sesion:
        caso_uso = ResponderCaptcha(repositorio=RepositorioSesionPlataformaSql(sesion))
        await caso_uso.ejecutar(sesion_id=sesion_id, respuesta=respuesta)

    print(f"Respuesta {respuesta!r} registrada para la sesion {sesion_id}.")
    print(
        "El trabajador, que esta esperando, la toma en los proximos segundos "
        "(INTERVALO_POLL_CAPTCHA_SEGUNDOS)."
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: responder_captcha_sesion_ejemplo.py <sesion_id> <respuesta>")
    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
