"""Adaptador de RepositorioDocumentosPago (CU-10, RI-11)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.pse.documentos import (
    ComprobanteReemplazado,
    ComprobanteVigente,
    DocumentosPagoCuenta,
    NotaDocumento,
    RepositorioDocumentosPago,
)
from app.dominio.pse.puertos import ComprobanteEmitido
from app.infraestructura.persistencia.modelos_documentos_pago import (
    ComprobanteReemplazadoModelo,
    NotaDocumentoModelo,
)
from app.infraestructura.persistencia.modelos_integracion import DocumentoFacturadorModelo
from app.infraestructura.persistencia.montos_comprobante_sql import montos_facturados_de_cuenta


class RepositorioDocumentosPagoSql(RepositorioDocumentosPago):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def _documento(self, cuenta_medica_id: int) -> DocumentoFacturadorModelo | None:
        return (
            await self._sesion.execute(
                sa.select(DocumentoFacturadorModelo).where(
                    DocumentoFacturadorModelo.cuenta_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()

    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        documento = await self._documento(cuenta_medica_id)
        if documento is None:
            return None
        nota = (
            await self._sesion.execute(
                sa.select(NotaDocumentoModelo).where(
                    NotaDocumentoModelo.documento_facturador_id == documento.id
                )
            )
        ).scalar_one_or_none()
        reemplazados = (
            await self._sesion.execute(
                sa.select(ComprobanteReemplazadoModelo)
                .where(ComprobanteReemplazadoModelo.documento_facturador_id == documento.id)
                .order_by(ComprobanteReemplazadoModelo.reemplazado_en)
            )
        ).scalars()
        valor_venta, igv, total = documento.valor_venta, documento.igv, documento.total
        if total is None:
            # Comprobante anterior al 2026-11-18: no guardo su monto.
            montos = await montos_facturados_de_cuenta(
                self._sesion, cuenta_medica_id, documento.tipo_documento_pago
            )
            if montos is not None:
                valor_venta, igv, total = (
                    montos.valor_venta,
                    montos.igv,
                    montos.total_facturado,
                )
        return DocumentosPagoCuenta(
            vigente=ComprobanteVigente(
                documento_id=documento.id,
                tipo_documento_pago=documento.tipo_documento_pago,
                serie=documento.serie,
                numero=documento.numero,
                fecha_emision=documento.fecha_emision,
                valor_venta=valor_venta,
                igv=igv,
                total=total,
            ),
            nota=(
                NotaDocumento(
                    tipo=nota.tipo,
                    serie=nota.serie,
                    numero=nota.numero,
                    monto=nota.monto,
                    fecha=nota.fecha,
                    motivo=nota.motivo,
                    registrado_en=nota.registrado_en,
                    registrado_por=nota.registrado_por,
                )
                if nota is not None
                else None
            ),
            reemplazados=[
                ComprobanteReemplazado(
                    tipo_documento_pago=r.tipo_documento_pago,
                    serie=r.serie,
                    numero=r.numero,
                    fecha_emision=r.fecha_emision,
                    reemplazado_en=r.reemplazado_en,
                    reemplazado_por=r.reemplazado_por,
                    motivo=r.motivo,
                )
                for r in reemplazados
            ],
        )

    async def guardar_nota(self, documento_id: int, nota: NotaDocumento) -> None:
        self._sesion.add(
            NotaDocumentoModelo(
                documento_facturador_id=documento_id,
                tipo=nota.tipo,
                serie=nota.serie,
                numero=nota.numero,
                monto=nota.monto,
                fecha=nota.fecha,
                motivo=nota.motivo,
                registrado_en=nota.registrado_en,
                registrado_por=nota.registrado_por,
            )
        )
        await self._sesion.flush()

    async def reemplazar(
        self, cuenta_medica_id: int, nuevo: ComprobanteEmitido, reemplazo: ComprobanteReemplazado
    ) -> None:
        documento = await self._documento(cuenta_medica_id)
        assert documento is not None, "el caso de uso ya verifico que existe"
        self._sesion.add(
            ComprobanteReemplazadoModelo(
                documento_facturador_id=documento.id,
                tipo_documento_pago=reemplazo.tipo_documento_pago,
                serie=reemplazo.serie,
                numero=reemplazo.numero,
                fecha_emision=reemplazo.fecha_emision,
                reemplazado_en=reemplazo.reemplazado_en,
                reemplazado_por=reemplazo.reemplazado_por,
                motivo=reemplazo.motivo,
            )
        )
        documento.tipo_documento_pago = nuevo.comprobante.tipo_documento_pago
        documento.serie = nuevo.comprobante.serie
        documento.numero = nuevo.comprobante.numero
        documento.fecha_emision = nuevo.comprobante.fecha_emision
        # El reemplazo guarda exactamente los montos que se enviaron al PSE.
        documento.valor_venta = nuevo.montos.valor_venta
        documento.igv = nuevo.montos.igv
        documento.total = nuevo.montos.total
        await self._sesion.flush()
