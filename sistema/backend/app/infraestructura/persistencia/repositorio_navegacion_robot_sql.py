"""Adaptador de RepositorioNavegacionRobot. Lo usan el backend (opcion del
administrador y consulta de las capturas) y el trabajador (que las guarda)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.plataformas.navegacion_robot import (
    CLAVE_OPCION_NAVEGACION_VISIBLE,
    ActividadRobot,
    PasoCapturado,
    PasoRobot,
    RepositorioNavegacionRobot,
)
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.modelos_robot import OpcionSistemaModelo, PasoRobotModelo

_ACTIVA = "true"
_INACTIVA = "false"


class RepositorioNavegacionRobotSql(RepositorioNavegacionRobot):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def navegacion_visible(self) -> bool:
        opcion = await self._sesion.get(OpcionSistemaModelo, CLAVE_OPCION_NAVEGACION_VISIBLE)
        return opcion is not None and opcion.valor == _ACTIVA

    async def fijar_navegacion_visible(self, activa: bool, actor: str) -> None:
        valor = _ACTIVA if activa else _INACTIVA
        opcion = await self._sesion.get(OpcionSistemaModelo, CLAVE_OPCION_NAVEGACION_VISIBLE)
        if opcion is None:
            self._sesion.add(
                OpcionSistemaModelo(
                    clave=CLAVE_OPCION_NAVEGACION_VISIBLE, valor=valor, actualizado_por=actor
                )
            )
        else:
            opcion.valor = valor
            opcion.actualizado_por = actor
        await self._sesion.flush()

    async def registrar_paso(self, paso: PasoCapturado) -> int:
        ultimo = await self._sesion.scalar(
            sa.select(sa.func.max(PasoRobotModelo.orden)).where(
                PasoRobotModelo.trabajo_id == paso.trabajo_id
            )
        )
        orden = int(ultimo or 0) + 1
        self._sesion.add(
            PasoRobotModelo(
                trabajo_id=paso.trabajo_id,
                orden=orden,
                plataforma=paso.plataforma,
                descripcion=paso.descripcion,
                url=paso.url,
                captura=paso.captura,
            )
        )
        await self._sesion.flush()
        return orden

    async def pasos(self, trabajo_id: int) -> list[PasoRobot]:
        # Sin la columna de la captura: la lista se pide cada dos segundos.
        filas = await self._sesion.execute(
            sa.select(
                PasoRobotModelo.orden,
                PasoRobotModelo.plataforma,
                PasoRobotModelo.descripcion,
                PasoRobotModelo.url,
                PasoRobotModelo.capturado_en,
            )
            .where(PasoRobotModelo.trabajo_id == trabajo_id)
            .order_by(PasoRobotModelo.orden)
        )
        return [PasoRobot(*fila) for fila in filas.all()]

    async def captura(self, trabajo_id: int, orden: int) -> bytes | None:
        paso = await self._sesion.scalar(
            sa.select(PasoRobotModelo).where(
                PasoRobotModelo.trabajo_id == trabajo_id, PasoRobotModelo.orden == orden
            )
        )
        return paso.captura if paso is not None else None

    async def actividad(self, maximo: int) -> list[ActividadRobot]:
        filas = await self._sesion.execute(
            sa.select(
                TrabajoModelo.id,
                TrabajoModelo.tipo,
                TrabajoModelo.estado,
                sa.func.min(PasoRobotModelo.capturado_en),
                sa.func.count(PasoRobotModelo.id),
            )
            .join(PasoRobotModelo, PasoRobotModelo.trabajo_id == TrabajoModelo.id)
            .group_by(TrabajoModelo.id, TrabajoModelo.tipo, TrabajoModelo.estado)
            .order_by(TrabajoModelo.id.desc())
            .limit(maximo)
        )
        return [
            ActividadRobot(
                trabajo_id=trabajo_id, tipo=tipo, estado=estado, iniciado_en=inicio, pasos=cantidad
            )
            for trabajo_id, tipo, estado, inicio, cantidad in filas.all()
        ]

    async def purgar_anteriores_a(self, limite: datetime) -> int:
        resultado = await self._sesion.execute(
            sa.delete(PasoRobotModelo).where(PasoRobotModelo.capturado_en < limite)
        )
        return int(getattr(resultado, "rowcount", 0) or 0)
