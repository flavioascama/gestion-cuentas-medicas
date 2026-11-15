"""Adaptador de RepositorioLoteRemision (Seccion 7.8)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.puertos import LoteParaRemitir, RepositorioLoteRemision
from app.dominio.orquestacion.valores import TipoTransicion
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    DocumentoFacturadorModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.transicion_cuentas_lote import (
    cuentas_de_documentos,
    transicionar_cuentas,
)


class RepositorioLoteRemisionSql(RepositorioLoteRemision):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_lote_para_remision(self, lote_id: int) -> LoteParaRemitir | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        if lote is None:
            return None
        resultado = await self._sesion.execute(
            sa.select(LoteDocumentoModelo.documento_id).where(
                LoteDocumentoModelo.lote_id == lote_id
            )
        )
        documento_ids = tuple(fila[0] for fila in resultado.all())
        return LoteParaRemitir(
            lote_id=lote.id,
            numero=lote.numero,
            estado=lote.estado,
            nombre_s01=lote.nombre_s01,
            sha256_s01=lote.sha256_s01,
            ruta_s01=lote.ruta_s01,
            documento_ids=documento_ids,
        )

    async def registrar_remision(
        self,
        lote_id: int,
        documento_ids: tuple[int, ...],
        exitosa: bool,
        motivo: str | None,
        instante: datetime,
    ) -> tuple[int, tuple[int, ...]]:
        acuse = AcuseTransmisionModelo(
            lote_id=lote_id,
            resultado_transferencia="ENVIADO" if exitosa else "ERROR_TRANSFERENCIA",
            motivo_transferencia=motivo,
            intentado_en=instante,
        )
        self._sesion.add(acuse)

        cuenta_medica_ids: tuple[int, ...] = ()
        if exitosa:
            await self._sesion.execute(
                sa.update(DocumentoFacturadorModelo)
                .where(DocumentoFacturadorModelo.id.in_(documento_ids))
                .values(
                    # Nunca sobreescribe un valor ya fijado (Seccion 6.2,
                    # 'la conserva en reenvios'); el disparador de la Fase 7
                    # lo impediria de todos modos si se intentara.
                    fecha_primer_envio=sa.func.coalesce(
                        DocumentoFacturadorModelo.fecha_primer_envio, instante.date()
                    )
                )
            )
            # T-03 (Tabla 58): FACTURADA -> ENVIADA, validada por el motor.
            cuenta_medica_ids = await cuentas_de_documentos(self._sesion, documento_ids)
            await transicionar_cuentas(self._sesion, cuenta_medica_ids, TipoTransicion.REMISION)
            await self._sesion.execute(
                sa.update(LoteFacturacionModelo)
                .where(LoteFacturacionModelo.id == lote_id)
                .values(estado="REMITIDO_IAFAS")
            )

        await self._sesion.flush()
        acuse_id = acuse.id
        await self._sesion.commit()
        return acuse_id, cuenta_medica_ids
