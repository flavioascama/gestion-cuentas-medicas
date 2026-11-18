"""A cual robot le toca atender la cola (2026-11-18).

Puede haber dos robots encendidos: el del servidor (un contenedor, sin
pantalla) y uno que corre en una computadora con pantalla, que es el unico
que puede abrir la ventana real del navegador. Nunca atienden a la vez: el
de la pantalla trabaja solo mientras el administrador pide ver la ventana
("Local"), y el del servidor le cede el turno mientras sepa que el otro esta
encendido. Asi cada trabajo lo hace un solo robot, con su propia sesion
guardada, y apagar el de la pantalla no deja la cola sin atender.

El robot con pantalla avisa que esta encendido con un latido cada pocos
segundos; la regla esta en `le_toca_atender` (dominio)."""

from __future__ import annotations

import asyncio

import structlog
from app.dominio.plataformas.navegacion_robot import (
    inicio_de_vigencia_latido,
    le_toca_atender,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

registro = structlog.get_logger(__name__)

_SEGUNDOS_ENTRE_LATIDOS = 5


class TurnoRobot:
    def __init__(
        self,
        fabrica_sesiones: async_sessionmaker[AsyncSession],
        reloj: Reloj,
        con_pantalla: bool,
    ) -> None:
        self._fabrica_sesiones = fabrica_sesiones
        self._reloj = reloj
        self._con_pantalla = con_pantalla

    async def me_toca(self) -> bool:
        try:
            async with self._fabrica_sesiones() as sesion:
                repositorio = RepositorioNavegacionRobotSql(sesion)
                opcion = await repositorio.opcion_navegacion()
                hay_otro = await repositorio.hay_robot_con_pantalla(
                    inicio_de_vigencia_latido(self._reloj)
                )
            return le_toca_atender(opcion, self._con_pantalla, hay_otro)
        except Exception:  # noqa: BLE001 -- sin la opcion a la vista, manda lo habitual
            registro.warning("turno_robot_no_disponible")
            return not self._con_pantalla

    async def latir(self) -> None:
        """Solo el robot con pantalla: avisa, mientras viva, que esta encendido."""
        while True:
            try:
                async with self._fabrica_sesiones() as sesion:
                    repositorio = RepositorioNavegacionRobotSql(sesion)
                    await repositorio.registrar_latido_pantalla(self._reloj.ahora())
                    await sesion.commit()
            except Exception:  # noqa: BLE001 -- un latido perdido no detiene al robot
                registro.debug("latido_robot_no_registrado")
            await asyncio.sleep(_SEGUNDOS_ENTRE_LATIDOS)
