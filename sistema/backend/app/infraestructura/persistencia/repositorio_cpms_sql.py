"""Adaptador de RepositorioCpms (Seccion 8.2)."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.cpms.puertos import DatosConfirmacionCodigo, RepositorioCpms, VersionCpms
from app.dominio.cpms.valores import CandidatoCpms, ProcedimientoCpms
from app.infraestructura.persistencia.modelos_cpms import CpmsProcedimientoModelo, CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    ProcedimientoFacturadoModelo,
)


class ErrorRepositorioCpms(Exception):
    pass


def _a_procedimiento_cpms(modelo: CpmsProcedimientoModelo) -> ProcedimientoCpms:
    return ProcedimientoCpms(
        codigo=modelo.codigo_procedimiento,
        denominacion=modelo.denominacion_procedimiento,
        codigo_grupo=modelo.codigo_grupo,
        nombre_grupo=modelo.nombre_grupo,
        codigo_seccion=modelo.codigo_seccion,
        nombre_seccion=modelo.nombre_seccion,
        codigo_subseccion=modelo.codigo_subseccion,
        nombre_subseccion=modelo.nombre_subseccion,
    )


class RepositorioCpmsSql(RepositorioCpms):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ultimo_monto_unitario(self, codigo: str, cuenta_medica_id: int) -> Decimal | None:
        """El precio con que se facturo por ultima vez ese codigo a la IAFAS
        de la cuenta (2026-11-18): se propone al confirmar el procedimiento,
        en vez de escribirlo cada vez. None si nunca se facturo."""
        iafas_de_la_cuenta = (
            sa.select(CuentaMedicaModelo.iafas_id)
            .where(CuentaMedicaModelo.id == cuenta_medica_id)
            .scalar_subquery()
        )
        monto: Decimal | None = await self._sesion.scalar(
            sa.select(ProcedimientoFacturadoModelo.monto_unitario)
            .join(
                CuentaMedicaModelo,
                CuentaMedicaModelo.id == ProcedimientoFacturadoModelo.cuenta_id,
            )
            .where(
                ProcedimientoFacturadoModelo.codigo_asignado == codigo,
                CuentaMedicaModelo.iafas_id == iafas_de_la_cuenta,
            )
            .order_by(ProcedimientoFacturadoModelo.id.desc())
            .limit(1)
        )
        return monto

    async def version_vigente(self) -> tuple[int, str]:
        resultado = await self._sesion.execute(
            sa.select(CpmsVersionModelo.id, CpmsVersionModelo.etiqueta)
            .order_by(CpmsVersionModelo.id.desc())
            .limit(1)
        )
        fila = resultado.first()
        if fila is None:
            raise ErrorRepositorioCpms("No hay ninguna version de CPMS cargada.")
        return fila[0], fila[1]

    async def obtener_candidato(self, cpms_version_id: int, codigo: str) -> CandidatoCpms | None:
        resultado = await self._sesion.execute(
            sa.select(CpmsProcedimientoModelo).where(
                CpmsProcedimientoModelo.cpms_version_id == cpms_version_id,
                CpmsProcedimientoModelo.codigo_procedimiento == codigo,
            )
        )
        modelo = resultado.scalar_one_or_none()
        if modelo is None:
            return None
        return CandidatoCpms(**asdict(_a_procedimiento_cpms(modelo)), puntaje=1.0, posicion=1)

    async def listar_procedimientos(self, cpms_version_id: int) -> list[ProcedimientoCpms]:
        resultado = await self._sesion.execute(
            sa.select(CpmsProcedimientoModelo).where(
                CpmsProcedimientoModelo.cpms_version_id == cpms_version_id
            )
        )
        return [_a_procedimiento_cpms(m) for m in resultado.scalars().all()]

    async def listar_versiones(self) -> list[VersionCpms]:
        resultado = await self._sesion.execute(
            sa.select(CpmsVersionModelo).order_by(CpmsVersionModelo.id.desc())
        )
        return [
            VersionCpms(
                id=m.id,
                etiqueta=m.etiqueta,
                conteo=m.conteo,
                archivos_origen=m.archivos_origen,
                creado_en=m.creado_en,
            )
            for m in resultado.scalars().all()
        ]

    async def confirmar_codigo(self, datos: DatosConfirmacionCodigo) -> int:
        registro = ProcedimientoFacturadoModelo(
            cuenta_id=datos.cuenta_id,
            descripcion_registrada=datos.descripcion_registrada,
            codigo_asignado=datos.codigo_asignado,
            cpms_version_id=datos.cpms_version_id,
            origen_codigo=datos.origen_codigo,
            posicion_aceptada=datos.posicion_aceptada,
            usuario_confirmo_id=datos.usuario_confirmo_id,
            confirmado_en=datos.confirmado_en,
            cantidad=datos.cantidad,
            monto_unitario=datos.monto_unitario,
            fecha=datos.fecha,
        )
        self._sesion.add(registro)
        await self._sesion.flush()
        id_creado = registro.id
        await self._sesion.commit()
        return id_creado
