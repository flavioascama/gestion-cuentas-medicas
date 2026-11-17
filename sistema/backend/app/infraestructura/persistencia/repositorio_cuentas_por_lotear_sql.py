"""Adaptador de RepositorioCuentasPorLotear: las cuentas facturadas que
todavia no estan en un lote en curso, para sugerir los lotes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.lotes_sugeridos import CuentaPorLotear, RepositorioCuentasPorLotear
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.montos_cuenta_sql import montos_por_cuenta

# Un lote en estos estados todavia no se remitio y sus cuentas siguen
# FACTURADA: no se sugieren otra vez. El observado por el validador no
# esta en curso; sus cuentas entran en un lote nuevo.
ESTADOS_LOTE_EN_CURSO = ("GENERADO", "CARGADO_VALIDADOR", "VALIDADO")


class RepositorioCuentasPorLotearSql(RepositorioCuentasPorLotear):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def cuentas_por_lotear(self) -> list[CuentaPorLotear]:
        en_lote_en_curso = (
            sa.select(LoteDocumentoModelo.id)
            .join(LoteFacturacionModelo, LoteFacturacionModelo.id == LoteDocumentoModelo.lote_id)
            .where(
                LoteDocumentoModelo.documento_id == DocumentoFacturadorModelo.id,
                LoteFacturacionModelo.estado.in_(ESTADOS_LOTE_EN_CURSO),
            )
            .exists()
        )
        filas = (
            await self._sesion.execute(
                sa.select(
                    CuentaMedicaModelo,
                    AseguradoModelo,
                    IafasModelo,
                    DocumentoFacturadorModelo.fecha_emision,
                )
                .join(
                    DocumentoFacturadorModelo,
                    DocumentoFacturadorModelo.cuenta_id == CuentaMedicaModelo.id,
                )
                .join(AseguradoModelo, AseguradoModelo.id == CuentaMedicaModelo.asegurado_id)
                .join(IafasModelo, IafasModelo.id == CuentaMedicaModelo.iafas_id)
                .where(CuentaMedicaModelo.estado == "FACTURADA", sa.not_(en_lote_en_curso))
                .order_by(CuentaMedicaModelo.identificacion_interna)
            )
        ).all()
        montos = await montos_por_cuenta(self._sesion, [fila[0].id for fila in filas])
        return [
            CuentaPorLotear(
                cuenta_id=cuenta.id,
                identificacion_interna=cuenta.identificacion_interna,
                nombres_asegurado=asegurado.nombres,
                apellidos_asegurado=asegurado.apellidos,
                iafas_id=iafas.id,
                iafas_codigo=iafas.codigo,
                iafas_razon_social=iafas.razon_social,
                fecha_emision=fecha_emision,
                monto=montos[cuenta.id],
            )
            for cuenta, asegurado, iafas, fecha_emision in filas
        ]
