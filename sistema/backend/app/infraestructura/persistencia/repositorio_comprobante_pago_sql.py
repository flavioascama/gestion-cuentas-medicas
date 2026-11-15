"""Adaptador de RepositorioComprobantePago (adenda de ingesta y
completitud, emision del comprobante de pago via el simulador PSE)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.pse.puertos import (
    ComprobantePse,
    ErrorComprobanteYaExiste,
    ErrorCuentaNoEncontrada,
    RepositorioComprobantePago,
)
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IpressModelo,
)


class RepositorioComprobantePagoSql(RepositorioComprobantePago):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        ipress = (await self._sesion.execute(sa.select(IpressModelo).limit(1))).scalar_one()
        return ipress.ruc, ipress.codigo_ipress

    async def guardar_comprobante(self, cuenta_id: int, comprobante: ComprobantePse) -> int:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            raise ErrorCuentaNoEncontrada(cuenta_id)

        # Chequeo explicito antes del INSERT, no un `except IntegrityError`
        # generico: `documento_facturador` tiene DOS restricciones unique
        # distintas (cuenta_id, y el compuesto ipress_id+tipo+serie+numero,
        # Seccion 6.2) -- capturar cualquier IntegrityError y asumir
        # siempre "esta cuenta ya tiene comprobante" reportaria mal un
        # choque de numeracion contra OTRA cuenta como si fuera este caso.
        ya_existe = await self._sesion.scalar(
            sa.select(sa.literal(True))
            .select_from(DocumentoFacturadorModelo)
            .where(DocumentoFacturadorModelo.cuenta_id == cuenta_id)
            .limit(1)
        )
        if ya_existe:
            raise ErrorComprobanteYaExiste(cuenta_id)

        documento = DocumentoFacturadorModelo(
            cuenta_id=cuenta_id,
            ipress_id=cuenta.ipress_id,
            tipo_documento_pago=comprobante.tipo_documento_pago,
            serie=comprobante.serie,
            numero=comprobante.numero,
            fecha_emision=comprobante.fecha_emision,
        )
        self._sesion.add(documento)
        await self._sesion.flush()
        await self._sesion.commit()
        return documento.id
