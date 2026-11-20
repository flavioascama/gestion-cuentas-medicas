"""Adaptador de RepositorioCuentasPorLotear: las cuentas facturadas que
todavia no estan en un lote en curso, para sugerir los lotes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.lotes_sugeridos import CuentaPorLotear, RepositorioCuentasPorLotear
from app.dominio.integracion.pendientes_lote import pendientes_para_lotear
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
)
from app.infraestructura.persistencia.montos_comprobante_sql import cotejo_de_cuenta
from app.infraestructura.persistencia.montos_cuenta_sql import montos_por_cuenta
from app.infraestructura.persistencia.vigencia_lote_sql import cuentas_en_lotes_vigentes


class RepositorioCuentasPorLotearSql(RepositorioCuentasPorLotear):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def cuentas_por_lotear(self) -> list[CuentaPorLotear]:
        # Las de un lote en curso que dejo de ser vigente vuelven a sugerirse.
        ocupadas = await cuentas_en_lotes_vigentes(self._sesion)
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
                .where(CuentaMedicaModelo.estado == "FACTURADA")
                .order_by(CuentaMedicaModelo.identificacion_interna)
            )
        ).all()
        filas = [fila for fila in filas if fila[0].id not in ocupadas]
        montos = await montos_por_cuenta(self._sesion, [fila[0].id for fila in filas])
        desfasadas = await self._con_comprobante_desfasado([fila[0].id for fila in filas])
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
                # Una cuenta facturada siempre tiene procedimientos: lo que puede
                # faltarle, en las anteriores al 2026-11-18, es el diagnostico.
                pendientes=pendientes_para_lotear(
                    bool(cuenta.diagnostico_principal_cie10), 1, cuenta.id in desfasadas
                ),
            )
            for cuenta, asegurado, iafas, fecha_emision in filas
        ]

    async def _con_comprobante_desfasado(self, cuenta_ids: list[int]) -> set[int]:
        # Una consulta por cuenta: solo calcula montos si el comprobante los guardo.
        desfasadas = set()
        for cuenta_id in cuenta_ids:
            if (await cotejo_de_cuenta(self._sesion, cuenta_id)).desfasado:
                desfasadas.add(cuenta_id)
        return desfasadas
