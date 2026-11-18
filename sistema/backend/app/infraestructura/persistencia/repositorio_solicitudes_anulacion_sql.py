"""Adaptador de RepositorioSolicitudesAnulacion (Seccion 5.2.4.1, RF-21,
Fase 28)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.cierre.puertos import RepositorioSolicitudesAnulacion
from app.dominio.cierre.valores import (
    DatosNuevaSolicitudAnulacion,
    EstadoSolicitudAnulacion,
    SolicitudAnulacion,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
)
from app.infraestructura.persistencia.modelos_liquidacion import SolicitudAnulacionModelo


def _a_valor(fila: SolicitudAnulacionModelo) -> SolicitudAnulacion:
    return SolicitudAnulacion(
        id=fila.id,
        cuenta_medica_id=fila.cuenta_medica_id,
        motivo=fila.motivo,
        estado=EstadoSolicitudAnulacion(fila.estado),
        solicitado_por=fila.solicitado_por,
        solicitado_en=fila.solicitado_en,
        resuelto_por=fila.resuelto_por,
        resuelto_en=fila.resuelto_en,
    )


class RepositorioSolicitudesAnulacionSql(RepositorioSolicitudesAnulacion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear(self, datos: DatosNuevaSolicitudAnulacion) -> int:
        fila = SolicitudAnulacionModelo(
            cuenta_medica_id=datos.cuenta_medica_id,
            motivo=datos.motivo,
            estado=EstadoSolicitudAnulacion.PENDIENTE.value,
            solicitado_por=datos.solicitado_por,
            solicitado_en=datos.solicitado_en,
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        return fila.id

    async def obtener(self, solicitud_id: int) -> SolicitudAnulacion | None:
        fila = await self._sesion.get(SolicitudAnulacionModelo, solicitud_id)
        return None if fila is None else _a_valor(fila)

    async def obtener_pendiente_por_cuenta(
        self, cuenta_medica_id: int
    ) -> SolicitudAnulacion | None:
        fila = (
            await self._sesion.execute(
                sa.select(SolicitudAnulacionModelo).where(
                    SolicitudAnulacionModelo.cuenta_medica_id == cuenta_medica_id,
                    SolicitudAnulacionModelo.estado == EstadoSolicitudAnulacion.PENDIENTE.value,
                )
            )
        ).scalar_one_or_none()
        return None if fila is None else _a_valor(fila)

    async def listar_pendientes(self) -> list[SolicitudAnulacion]:
        filas = await self._sesion.execute(
            sa.select(SolicitudAnulacionModelo, CuentaMedicaModelo, AseguradoModelo)
            .join(
                CuentaMedicaModelo,
                CuentaMedicaModelo.id == SolicitudAnulacionModelo.cuenta_medica_id,
            )
            .join(AseguradoModelo, AseguradoModelo.id == CuentaMedicaModelo.asegurado_id)
            .where(SolicitudAnulacionModelo.estado == EstadoSolicitudAnulacion.PENDIENTE.value)
            .order_by(SolicitudAnulacionModelo.solicitado_en)
        )
        return [
            replace(
                _a_valor(solicitud),
                identificacion_interna=cuenta.identificacion_interna,
                asegurado=f"{asegurado.nombres} {asegurado.apellidos}",
            )
            for solicitud, cuenta, asegurado in filas.all()
        ]

    async def resolver(
        self, solicitud_id: int, aprobada: bool, resuelto_por: str, resuelto_en: datetime
    ) -> None:
        nuevo_estado = (
            EstadoSolicitudAnulacion.APROBADA if aprobada else EstadoSolicitudAnulacion.RECHAZADA
        )
        await self._sesion.execute(
            sa.update(SolicitudAnulacionModelo)
            .where(SolicitudAnulacionModelo.id == solicitud_id)
            .values(estado=nuevo_estado.value, resuelto_por=resuelto_por, resuelto_en=resuelto_en)
        )
