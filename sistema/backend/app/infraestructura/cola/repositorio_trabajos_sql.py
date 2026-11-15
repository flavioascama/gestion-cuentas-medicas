"""Adaptador de RepositorioTrabajos (Seccion 5.2, 6.1, 6.2): la cola
transaccional sobre la tabla `trabajo`, con `SELECT ... FOR UPDATE SKIP
LOCKED` (AD-03). Lo usan tanto el backend, para encolar
(`RemitirLote`, `SolicitarVerificacionCobertura`), como el trabajador de
`sistema/automatizacion/`, para consumir -- el mismo adaptador, importado
como dependencia de ese proceso separado (AD-02)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.puertos_comunes import DetalleTrabajo, RepositorioTrabajos, TrabajoPendiente
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo

_LONGITUD_MAXIMA_ERROR = 1000


class RepositorioTrabajosSql(RepositorioTrabajos):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def encolar(
        self, tipo: str, carga_util: dict[str, Any], proximo_intento: datetime
    ) -> int:
        trabajo = TrabajoModelo(tipo=tipo, carga_util=carga_util, proximo_intento=proximo_intento)
        self._sesion.add(trabajo)
        await self._sesion.flush()
        id_creado = trabajo.id
        await self._sesion.commit()
        return id_creado

    async def obtener(self, trabajo_id: int) -> DetalleTrabajo | None:
        fila = await self._sesion.get(TrabajoModelo, trabajo_id)
        if fila is None:
            return None
        return DetalleTrabajo(
            id=fila.id,
            tipo=fila.tipo,
            carga_util=fila.carga_util,
            estado=fila.estado,
            intentos=fila.intentos,
            error=fila.error,
            creado_en=fila.creado_en,
            actualizado_en=fila.actualizado_en,
        )

    async def tomar_siguiente(self, tipos: tuple[str, ...]) -> TrabajoPendiente | None:
        resultado = await self._sesion.execute(
            sa.select(TrabajoModelo)
            .where(
                TrabajoModelo.estado == "PENDIENTE",
                TrabajoModelo.proximo_intento <= sa.func.now(),
                TrabajoModelo.tipo.in_(tipos),
            )
            .order_by(TrabajoModelo.proximo_intento)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        fila = resultado.scalar_one_or_none()
        if fila is None:
            await self._sesion.commit()
            return None

        fila.estado = "EN_PROCESO"
        trabajo_pendiente = TrabajoPendiente(
            id=fila.id,
            tipo=fila.tipo,
            carga_util=fila.carga_util,
            intentos=fila.intentos,
            creado_en=fila.creado_en,
        )
        await self._sesion.commit()
        return trabajo_pendiente

    async def marcar_completado(self, trabajo_id: int) -> None:
        await self._sesion.execute(
            sa.update(TrabajoModelo)
            .where(TrabajoModelo.id == trabajo_id)
            .values(estado="COMPLETADO")
        )
        await self._sesion.commit()

    async def marcar_para_reintento(
        self, trabajo_id: int, error: str, proximo_intento: datetime
    ) -> None:
        await self._sesion.execute(
            sa.update(TrabajoModelo)
            .where(TrabajoModelo.id == trabajo_id)
            .values(
                estado="PENDIENTE",
                intentos=TrabajoModelo.intentos + 1,
                error=error[:_LONGITUD_MAXIMA_ERROR],
                proximo_intento=proximo_intento,
            )
        )
        await self._sesion.commit()

    async def marcar_agotado(self, trabajo_id: int, error: str) -> None:
        await self._sesion.execute(
            sa.update(TrabajoModelo)
            .where(TrabajoModelo.id == trabajo_id)
            .values(
                estado="AGOTADO",
                intentos=TrabajoModelo.intentos + 1,
                error=error[:_LONGITUD_MAXIMA_ERROR],
            )
        )
        await self._sesion.commit()

    async def marcar_sin_resultado(self, trabajo_id: int, mensaje: str) -> None:
        """La plataforma respondio con un resultado definitivo negativo (por
        ejemplo, asegurado no encontrado): terminal, sin reintentos, y no
        cuenta como falla del proceso de automatizacion (RNF-20)."""
        await self._sesion.execute(
            sa.update(TrabajoModelo)
            .where(TrabajoModelo.id == trabajo_id)
            .values(
                estado="SIN_RESULTADO",
                intentos=TrabajoModelo.intentos + 1,
                error=mensaje[:_LONGITUD_MAXIMA_ERROR],
            )
        )
        await self._sesion.commit()

    async def marcar_requiere_sesion(self, trabajo_id: int, motivo: str | None = None) -> None:
        valores: dict[str, object] = {"estado": "REQUIERE_SESION"}
        if motivo:
            valores["error"] = motivo[:_LONGITUD_MAXIMA_ERROR]
        await self._sesion.execute(
            sa.update(TrabajoModelo).where(TrabajoModelo.id == trabajo_id).values(**valores)
        )
        await self._sesion.commit()

    async def reactivar_requieren_sesion(self, tipos: tuple[str, ...]) -> int:
        resultado = await self._sesion.execute(
            sa.update(TrabajoModelo)
            .where(TrabajoModelo.estado == "REQUIERE_SESION", TrabajoModelo.tipo.in_(tipos))
            .values(estado="PENDIENTE", proximo_intento=sa.func.now())
        )
        await self._sesion.commit()
        return cast(CursorResult[Any], resultado).rowcount
