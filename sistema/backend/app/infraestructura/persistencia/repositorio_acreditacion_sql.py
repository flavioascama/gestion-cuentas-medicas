"""Adaptador de RepositorioAcreditacion (Seccion 8.1)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dominio.acreditacion.puertos import AcreditacionRegistrada, RepositorioAcreditacion
from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion, ResultadoAcreditacion
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
)


class RepositorioAcreditacionSql(RepositorioAcreditacion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_contexto_cuenta(
        self, cuenta_medica_id: int
    ) -> ContextoCuentaAcreditacion | None:
        resultado = await self._sesion.execute(
            sa.select(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_medica_id)
            .options(
                selectinload(CuentaMedicaModelo.asegurado), selectinload(CuentaMedicaModelo.iafas)
            )
        )
        cuenta = resultado.scalar_one_or_none()
        if cuenta is None:
            return None
        tiene_comprobante = await self._sesion.scalar(
            sa.select(sa.exists().where(DocumentoFacturadorModelo.cuenta_id == cuenta.id))
        )
        return ContextoCuentaAcreditacion(
            cuenta_medica_id=cuenta.id,
            tipo_documento_paciente=cuenta.asegurado.tipo_documento,
            numero_documento_paciente=cuenta.asegurado.numero_documento,
            codigo_iafas=cuenta.iafas.codigo,
            estado_cuenta=cuenta.estado,
            tiene_comprobante=bool(tiene_comprobante),
        )

    async def existe_acreditacion(self, cuenta_medica_id: int) -> bool:
        resultado = await self._sesion.execute(
            sa.select(sa.exists().where(AcreditacionModelo.cuenta_id == cuenta_medica_id))
        )
        return bool(resultado.scalar_one())

    async def guardar_acreditacion(
        self,
        cuenta_medica_id: int,
        resultado: ResultadoAcreditacion,
        instante: datetime,
        duracion_ms: int,
        componente_ejecutor: str,
    ) -> int:
        acreditacion = AcreditacionModelo(
            cuenta_id=cuenta_medica_id,
            condicion_cobertura=resultado.condicion_cobertura,
            codigo_autorizacion=resultado.codigo_autorizacion,
            tipo_documento_autorizacion=resultado.tipo_documento_autorizacion,
            codigo_asegurado=resultado.codigo_asegurado,
            tipo_afiliacion=resultado.tipo_afiliacion,
            plan=resultado.plan,
            vigente_desde=resultado.vigente_desde,
            vigente_hasta=resultado.vigente_hasta,
            tipo_copago=resultado.tipo_copago,
            monto_copago_fijo=resultado.monto_copago_fijo,
            porcentaje_coaseguro=resultado.porcentaje_coaseguro,
            preexistencias=resultado.preexistencias,
            instante=instante,
            duracion_ms=duracion_ms,
            componente_ejecutor=componente_ejecutor,
            ruta_evidencia=resultado.ruta_evidencia,
        )
        self._sesion.add(acreditacion)
        await self._sesion.flush()
        id_creado = acreditacion.id
        await self._sesion.commit()
        return id_creado

    async def obtener_acreditacion(self, cuenta_medica_id: int) -> AcreditacionRegistrada | None:
        resultado = await self._sesion.execute(
            sa.select(AcreditacionModelo)
            .where(AcreditacionModelo.cuenta_id == cuenta_medica_id)
            .order_by(AcreditacionModelo.id.desc())
            .limit(1)
        )
        fila = resultado.scalar_one_or_none()
        if fila is None:
            return None
        return AcreditacionRegistrada(
            id=fila.id,
            instante=fila.instante,
            componente_ejecutor=fila.componente_ejecutor,
            resultado=ResultadoAcreditacion(
                condicion_cobertura=fila.condicion_cobertura,
                codigo_autorizacion=fila.codigo_autorizacion,
                tipo_documento_autorizacion=fila.tipo_documento_autorizacion,
                codigo_asegurado=fila.codigo_asegurado,
                tipo_afiliacion=fila.tipo_afiliacion,
                plan=fila.plan,
                vigente_desde=fila.vigente_desde,
                vigente_hasta=fila.vigente_hasta,
                tipo_copago=fila.tipo_copago,
                monto_copago_fijo=fila.monto_copago_fijo,
                porcentaje_coaseguro=fila.porcentaje_coaseguro,
                preexistencias=fila.preexistencias,
                ruta_evidencia=fila.ruta_evidencia,
            ),
        )
