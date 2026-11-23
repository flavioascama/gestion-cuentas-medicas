"""Las atenciones que el administrador cargo con un Excel, guardadas en
el sistema, sumadas a las que entrega el sistema hospitalario: quien importa
las ve en una sola lista."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    ErrorSistemaHospitalarioNoDisponible,
    FuenteAtenciones,
    ResumenAtencionHospitalaria,
)
from app.infraestructura.persistencia.modelos_atenciones_cargadas import AtencionCargadaModelo
from app.infraestructura.sistema_hospitalario.esquema_atencion import AtencionJson


async def codigos_ya_cargados(sesion: AsyncSession, atencion_ids: list[str]) -> set[str]:
    filas = await sesion.scalars(
        sa.select(AtencionCargadaModelo.atencion_id).where(
            AtencionCargadaModelo.atencion_id.in_(atencion_ids)
        )
    )
    return set(filas.all())


async def guardar_atenciones(
    sesion: AsyncSession, atenciones: list[AtencionJson], actor: str
) -> None:
    ahora = datetime.now(UTC)
    for atencion in atenciones:
        sesion.add(
            AtencionCargadaModelo(
                atencion_id=atencion.atencion_id.strip(),
                datos=atencion.model_dump_json(),
                cargado_por=actor,
                cargado_en=ahora,
            )
        )
    await sesion.commit()


class FuenteAtencionesConCargadas(FuenteAtenciones):
    def __init__(self, sesion: AsyncSession, sistema: FuenteAtenciones) -> None:
        self._sesion = sesion
        self._sistema = sistema

    async def _cargadas(self) -> list[AtencionJson]:
        filas = await self._sesion.scalars(
            sa.select(AtencionCargadaModelo.datos).order_by(AtencionCargadaModelo.id)
        )
        return [AtencionJson.model_validate_json(datos) for datos in filas.all()]

    async def listar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        cargadas = [
            ResumenAtencionHospitalaria(
                atencion_id=a.atencion_id,
                tipo_atencion=a.tipo_atencion,
                fecha_prestacion=a.fecha_prestacion,
                paciente=a.paciente.a_valor(),
                iafas_codigo=a.iafas_codigo,
            )
            for a in await self._cargadas()
            if documento is None or a.paciente.numero_documento == documento
        ]
        try:
            del_sistema = await self._sistema.listar(documento)
        except ErrorSistemaHospitalarioNoDisponible:
            # Sin el sistema hospitalario se sigue pudiendo importar lo cargado.
            if not cargadas:
                raise
            del_sistema = []
        return cargadas + del_sistema

    async def obtener(self, atencion_id: str) -> AtencionHospitalaria | None:
        datos = await self._sesion.scalar(
            sa.select(AtencionCargadaModelo.datos).where(
                AtencionCargadaModelo.atencion_id == atencion_id
            )
        )
        if datos is not None:
            return AtencionJson.model_validate_json(datos).a_valor()
        return await self._sistema.obtener(atencion_id)
