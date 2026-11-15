"""Adaptador de RepositorioCuentasConsulta (Fase 18, Seccion 11)."""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.dominio.integracion.puertos_consulta import (
    DetalleCuenta,
    ProcedimientoResumen,
    ProductoResumen,
    RepositorioCuentasConsulta,
    ResumenCuenta,
)
from app.infraestructura.persistencia.modelos_catalogo_gtin import CatalogoGtinProductoModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, IafasModelo


class RepositorioCuentasConsultaSql(RepositorioCuentasConsulta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(
        self,
        estado: str | None,
        iafas_codigo: str | None = None,
        fecha_prestacion: date | None = None,
        estados: tuple[str, ...] | None = None,
    ) -> list[ResumenCuenta]:
        consulta = (
            sa.select(CuentaMedicaModelo)
            .join(IafasModelo)
            .options(
                selectinload(CuentaMedicaModelo.asegurado),
                contains_eager(CuentaMedicaModelo.iafas),
            )
            .order_by(CuentaMedicaModelo.creado_en.desc())
        )
        if estado is not None:
            consulta = consulta.where(CuentaMedicaModelo.estado == estado)
        if estados is not None:
            consulta = consulta.where(CuentaMedicaModelo.estado.in_(estados))
        if iafas_codigo is not None:
            consulta = consulta.where(IafasModelo.codigo == iafas_codigo)
        if fecha_prestacion is not None:
            consulta = consulta.where(CuentaMedicaModelo.fecha_prestacion == fecha_prestacion)
        resultado = await self._sesion.execute(consulta)
        return [
            ResumenCuenta(
                id=cuenta.id,
                identificacion_interna=cuenta.identificacion_interna,
                estado=cuenta.estado,
                fecha_prestacion=cuenta.fecha_prestacion,
                nombres_asegurado=cuenta.asegurado.nombres,
                apellidos_asegurado=cuenta.asegurado.apellidos,
                iafas_codigo=cuenta.iafas.codigo,
                iafas_razon_social=cuenta.iafas.razon_social,
            )
            for cuenta in resultado.scalars().unique().all()
        ]

    async def obtener(self, cuenta_medica_id: int) -> DetalleCuenta | None:
        resultado = await self._sesion.execute(
            sa.select(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_medica_id)
            .options(
                selectinload(CuentaMedicaModelo.asegurado),
                selectinload(CuentaMedicaModelo.iafas),
                selectinload(CuentaMedicaModelo.ipress),
                selectinload(CuentaMedicaModelo.procedimientos),
            )
        )
        cuenta = resultado.scalar_one_or_none()
        if cuenta is None:
            return None
        return DetalleCuenta(
            id=cuenta.id,
            identificacion_interna=cuenta.identificacion_interna,
            estado=cuenta.estado,
            fecha_prestacion=cuenta.fecha_prestacion,
            hora_prestacion=cuenta.hora_prestacion,
            numero_historia_clinica=cuenta.numero_historia_clinica,
            diagnostico_principal_cie10=cuenta.diagnostico_principal_cie10,
            nombres_asegurado=cuenta.asegurado.nombres,
            apellidos_asegurado=cuenta.asegurado.apellidos,
            tipo_documento_asegurado=cuenta.asegurado.tipo_documento,
            numero_documento_asegurado=cuenta.asegurado.numero_documento,
            iafas_codigo=cuenta.iafas.codigo,
            iafas_razon_social=cuenta.iafas.razon_social,
            ipress_codigo=cuenta.ipress.codigo_ipress,
            procedimientos=tuple(
                ProcedimientoResumen(
                    codigo_asignado=p.codigo_asignado,
                    descripcion_registrada=p.descripcion_registrada,
                    cantidad=p.cantidad,
                )
                for p in cuenta.procedimientos
            ),
            productos=await self._productos(cuenta_medica_id),
        )

    async def _productos(self, cuenta_medica_id: int) -> tuple[ProductoResumen, ...]:
        # Sin relationship() hacia CuentaMedicaModelo a proposito (Fase
        # 17, mismo motivo que procedimiento_facturado/cpms_version): se
        # consulta aparte.
        resultado = await self._sesion.execute(
            sa.select(ProductoFacturadoModelo, CatalogoGtinProductoModelo.nombre)
            .outerjoin(
                CatalogoGtinProductoModelo,
                sa.and_(
                    CatalogoGtinProductoModelo.version_id
                    == ProductoFacturadoModelo.catalogo_gtin_version_id,
                    CatalogoGtinProductoModelo.codigo == ProductoFacturadoModelo.codigo_producto,
                ),
            )
            .where(ProductoFacturadoModelo.cuenta_medica_id == cuenta_medica_id)
            .order_by(ProductoFacturadoModelo.correlativo)
        )
        return tuple(
            ProductoResumen(
                tipo_producto=p.tipo_producto,
                catalogo=p.catalogo,
                codigo_producto=p.codigo_producto,
                cantidad_venta=str(p.cantidad_venta),
                id=p.id,
                correlativo=p.correlativo,
                nombre=nombre,
                fecha_dispensacion=p.fecha_dispensacion,
                monto_presentado=str(p.monto_presentado),
            )
            for p, nombre in resultado.all()
        )
