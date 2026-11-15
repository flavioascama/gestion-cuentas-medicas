"""Adaptador de RepositorioRechazoCuenta (T-04/T-05): el rechazo mas
reciente de la IAFAS sobre algun lote que incluyo el comprobante de la
cuenta. Lee el acuse (respuesta del receptor), no el evento, porque el
motivo y el instante ya viven ahi desde la Fase 12."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.orquestacion.puertos import RechazoCuenta, RepositorioRechazoCuenta
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    DocumentoFacturadorModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)


class RepositorioRechazoCuentaSql(RepositorioRechazoCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_ultimo_rechazo(self, cuenta_medica_id: int) -> RechazoCuenta | None:
        fila = (
            await self._sesion.execute(
                sa.select(
                    LoteFacturacionModelo.id,
                    LoteFacturacionModelo.numero,
                    AcuseTransmisionModelo.motivo_receptor,
                    AcuseTransmisionModelo.respondido_en,
                )
                .join(
                    AcuseTransmisionModelo,
                    AcuseTransmisionModelo.lote_id == LoteFacturacionModelo.id,
                )
                .join(LoteDocumentoModelo, LoteDocumentoModelo.lote_id == LoteFacturacionModelo.id)
                .join(
                    DocumentoFacturadorModelo,
                    DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
                )
                .where(
                    DocumentoFacturadorModelo.cuenta_id == cuenta_medica_id,
                    AcuseTransmisionModelo.respuesta_receptor == "RECHAZADO",
                )
                .order_by(AcuseTransmisionModelo.respondido_en.desc().nulls_last())
                .limit(1)
            )
        ).first()
        if fila is None:
            return None
        lote_id, numero, motivo, respondido_en = fila
        return RechazoCuenta(
            lote_id=lote_id, numero_lote=numero, motivo=motivo, rechazado_en=respondido_en
        )
