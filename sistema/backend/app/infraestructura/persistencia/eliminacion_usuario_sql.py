"""Adaptador de EliminacionUsuarios."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.eliminacion_usuario import EliminacionUsuarios
from app.dominio.acceso.entidades import Usuario
from app.infraestructura.persistencia.modelos_acceso import UsuarioModelo
from app.infraestructura.persistencia.modelos_integracion import (
    EventoModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.modelos_observaciones import ObservacionModelo


class EliminacionUsuariosSql(EliminacionUsuarios):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def tiene_actividad(self, usuario: Usuario) -> bool:
        nombre = usuario.nombre_usuario
        consultas = (
            sa.select(EventoModelo.evento_id).where(
                sa.or_(EventoModelo.actor == nombre, EventoModelo.usuario_origen == nombre)
            ),
            sa.select(ProcedimientoFacturadoModelo.id).where(
                ProcedimientoFacturadoModelo.usuario_confirmo_id == usuario.id
            ),
            sa.select(ObservacionModelo.id).where(
                ObservacionModelo.responsable_usuario_id == usuario.id
            ),
        )
        for consulta in consultas:
            if await self._sesion.scalar(consulta.limit(1)) is not None:
                return True
        return False

    async def eliminar(self, usuario_id: int) -> None:
        await self._sesion.execute(sa.delete(UsuarioModelo).where(UsuarioModelo.id == usuario_id))
        await self._sesion.commit()
