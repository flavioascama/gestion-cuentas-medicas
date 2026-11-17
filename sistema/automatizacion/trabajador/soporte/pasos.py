"""Capturas de la navegacion del robot (2026-11-17).

Si el administrador activo la opcion, cada paso del robot deja una captura
de su navegador, cifrada en la base (C-05, C-12), para que quien opera el
sistema vea que el robot entra a la plataforma y hace el flujo. Con la
opcion apagada, que es lo habitual, esto no hace nada.

Guardar una captura nunca puede hacer fallar al robot: si la base o la
pagina no responden, el paso se omite y queda un aviso en el registro."""

from __future__ import annotations

import structlog
from app.dominio.plataformas.navegacion_robot import (
    PasoCapturado,
    limite_de_retencion,
    url_sin_consulta,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)
from playwright.async_api import Page
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

registro = structlog.get_logger(__name__)

# Suficiente para leer la pantalla; cada captura pesa decenas de KB.
_CALIDAD_JPEG = 60


class RegistradorPasos:
    def __init__(self, fabrica_sesiones: async_sessionmaker[AsyncSession], reloj: Reloj) -> None:
        self._fabrica_sesiones = fabrica_sesiones
        self._reloj = reloj
        # El trabajador atiende un trabajo a la vez: basta con recordar cual.
        self._trabajo_id: int | None = None

    async def iniciar(self, trabajo_id: int) -> None:
        """Al tomar un trabajo: consulta si la opcion esta activa y, de
        paso, borra las capturas que ya cumplieron su retencion."""
        self._trabajo_id = None
        try:
            async with self._fabrica_sesiones() as sesion:
                repositorio = RepositorioNavegacionRobotSql(sesion)
                if not await repositorio.navegacion_visible():
                    return
                await repositorio.purgar_anteriores_a(limite_de_retencion(self._reloj))
                await sesion.commit()
            self._trabajo_id = trabajo_id
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning("navegacion_robot_no_disponible", trabajo_id=trabajo_id)

    def terminar(self) -> None:
        self._trabajo_id = None

    async def capturar(self, pagina: Page, plataforma: str, descripcion: str) -> None:
        if self._trabajo_id is None:
            return
        try:
            imagen = await pagina.screenshot(type="jpeg", quality=_CALIDAD_JPEG)
            paso = PasoCapturado(
                trabajo_id=self._trabajo_id,
                plataforma=plataforma,
                descripcion=descripcion,
                url=url_sin_consulta(pagina.url),
                captura=imagen,
            )
            async with self._fabrica_sesiones() as sesion:
                await RepositorioNavegacionRobotSql(sesion).registrar_paso(paso)
                await sesion.commit()
        except Exception:  # noqa: BLE001 -- ver el docstring del modulo
            registro.warning(
                "paso_robot_no_capturado", trabajo_id=self._trabajo_id, paso=descripcion
            )
