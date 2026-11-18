"""Adaptadores de RepositorioCatalogoMotivos y RepositorioObservaciones
(Seccion 5.2.4.2, Fase 26)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from app.dominio.observaciones.puertos import RepositorioCatalogoMotivos, RepositorioObservaciones
from app.dominio.observaciones.valores import (
    DatosNuevaObservacion,
    MotivoObservacion,
    Naturaleza,
    Observacion,
)
from app.infraestructura.persistencia.modelos_acceso import UsuarioModelo
from app.infraestructura.persistencia.modelos_observaciones import (
    CatalogoMotivoObservacionModelo,
    ObservacionModelo,
)


def _a_motivo(modelo: CatalogoMotivoObservacionModelo) -> MotivoObservacion:
    return MotivoObservacion(
        codigo=modelo.codigo,
        descripcion=modelo.descripcion,
        naturaleza=Naturaleza(modelo.naturaleza),
    )


def _a_observacion(modelo: ObservacionModelo) -> Observacion:
    return Observacion(
        id=modelo.id,
        cuenta_medica_id=modelo.cuenta_medica_id,
        motivo_codigo=modelo.motivo_codigo,
        naturaleza=Naturaleza(modelo.naturaleza),
        es_parcial=modelo.es_parcial,
        detalle_campo_objetado=modelo.detalle_campo_objetado,
        responsable_rol=NombreRol(modelo.responsable_rol),
        responsable_usuario_id=modelo.responsable_usuario_id,
        estado=modelo.estado,
        respuesta_texto=modelo.respuesta_texto,
        respuesta_sustento=modelo.respuesta_sustento,
        registrado_en=modelo.registrado_en,
        respondido_en=modelo.respondido_en,
    )


class RepositorioCatalogoMotivosSql(RepositorioCatalogoMotivos):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener(self, codigo: str) -> MotivoObservacion | None:
        modelo = (
            await self._sesion.execute(
                sa.select(CatalogoMotivoObservacionModelo).where(
                    CatalogoMotivoObservacionModelo.codigo == codigo
                )
            )
        ).scalar_one_or_none()
        return None if modelo is None else _a_motivo(modelo)

    async def listar(self) -> list[MotivoObservacion]:
        modelos = (
            (
                await self._sesion.execute(
                    sa.select(CatalogoMotivoObservacionModelo).order_by(
                        CatalogoMotivoObservacionModelo.codigo
                    )
                )
            )
            .scalars()
            .all()
        )
        return [_a_motivo(m) for m in modelos]


class RepositorioObservacionesSql(RepositorioObservaciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear(self, datos: DatosNuevaObservacion) -> int:
        modelo = ObservacionModelo(
            cuenta_medica_id=datos.cuenta_medica_id,
            motivo_codigo=datos.motivo_codigo,
            naturaleza=datos.naturaleza.value,
            es_parcial=datos.es_parcial,
            detalle_campo_objetado=datos.detalle_campo_objetado,
            responsable_rol=datos.responsable_rol.value,
            estado="ABIERTA",
            registrado_en=datos.registrado_en,
        )
        self._sesion.add(modelo)
        await self._sesion.flush()
        return modelo.id

    async def obtener(self, observacion_id: int) -> Observacion | None:
        modelo = await self._sesion.get(ObservacionModelo, observacion_id)
        return None if modelo is None else _a_observacion(modelo)

    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[Observacion]:
        filas = await self._sesion.execute(
            sa.select(ObservacionModelo, UsuarioModelo.nombres)
            .outerjoin(UsuarioModelo, UsuarioModelo.id == ObservacionModelo.responsable_usuario_id)
            .where(ObservacionModelo.cuenta_medica_id == cuenta_medica_id)
            .order_by(ObservacionModelo.registrado_en)
        )
        return [
            replace(_a_observacion(modelo), responsable_nombres=nombres)
            for modelo, nombres in filas.all()
        ]

    async def reasignar(
        self,
        observacion_id: int,
        naturaleza: Naturaleza,
        responsable_rol: NombreRol,
        responsable_usuario_id: int | None,
    ) -> None:
        await self._sesion.execute(
            sa.update(ObservacionModelo)
            .where(ObservacionModelo.id == observacion_id)
            .values(
                naturaleza=naturaleza.value,
                responsable_rol=responsable_rol.value,
                responsable_usuario_id=responsable_usuario_id,
            )
        )

    async def responder(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: str | None,
        respondido_en: datetime,
    ) -> None:
        await self._sesion.execute(
            sa.update(ObservacionModelo)
            .where(ObservacionModelo.id == observacion_id)
            .values(
                estado="RESPONDIDA",
                respuesta_texto=respuesta_texto,
                respuesta_sustento=respuesta_sustento,
                respondido_en=respondido_en,
            )
        )
