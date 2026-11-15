"""Adaptador de RepositorioMonitoreoRespuesta (Seccion 8.3)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.puertos import (
    ContextoLoteMonitoreo,
    ErrorLoteNoMonitoreable,
    RepositorioMonitoreoRespuesta,
)
from app.dominio.orquestacion.valores import TipoTransicion
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    IafasModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.transicion_cuentas_lote import (
    cuentas_de_documentos,
    transicionar_cuentas,
)


class RepositorioMonitoreoRespuestaSql(RepositorioMonitoreoRespuesta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_contexto_lote(self, lote_id: int) -> ContextoLoteMonitoreo | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        if lote is None:
            return None
        iafas = await self._sesion.get(IafasModelo, lote.iafas_id)
        assert iafas is not None  # llave foranea NOT NULL: siempre existe
        # Solo se monitorea un lote ya REMITIDO_IAFAS (Fase 13): RemitirLote
        # exige nombre_s01 no nulo antes de remitir, asi que aqui siempre
        # esta presente.
        assert lote.nombre_s01 is not None
        return ContextoLoteMonitoreo(
            lote_id=lote.id,
            numero=lote.numero,
            nombre_s01=lote.nombre_s01,
            ventana_monitoreo_horas=iafas.ventana_monitoreo_horas,
        )

    async def _buscar_acuse_pendiente(self, lote_id: int) -> AcuseTransmisionModelo:
        acuse = (
            await self._sesion.execute(
                sa.select(AcuseTransmisionModelo)
                .where(
                    AcuseTransmisionModelo.lote_id == lote_id,
                    AcuseTransmisionModelo.resultado_transferencia == "ENVIADO",
                    AcuseTransmisionModelo.respuesta_receptor.is_(None),
                )
                .order_by(AcuseTransmisionModelo.intentado_en.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if acuse is None:
            raise ErrorLoteNoMonitoreable(
                f"El lote {lote_id} no tiene un acuse de transmision exitoso pendiente de "
                "respuesta del receptor."
            )
        return acuse

    async def _cuentas_del_lote(self, lote_id: int) -> tuple[int, ...]:
        resultado = await self._sesion.execute(
            sa.select(LoteDocumentoModelo.documento_id).where(
                LoteDocumentoModelo.lote_id == lote_id
            )
        )
        documento_ids = tuple(fila[0] for fila in resultado.all())
        return await cuentas_de_documentos(self._sesion, documento_ids)

    async def aplicar_respuesta(
        self, lote_id: int, estado_receptor: str, motivo: str | None, instante: datetime
    ) -> tuple[int, tuple[int, ...]]:
        acuse = await self._buscar_acuse_pendiente(lote_id)
        acuse.respuesta_receptor = estado_receptor
        acuse.motivo_receptor = motivo
        acuse.respondido_en = instante

        await self._sesion.execute(
            sa.update(LoteFacturacionModelo)
            .where(LoteFacturacionModelo.id == lote_id)
            .values(estado=estado_receptor)
        )

        cuenta_medica_ids: tuple[int, ...] = ()
        if estado_receptor == "RECHAZADO":
            cuenta_medica_ids = await self._cuentas_del_lote(lote_id)
            await transicionar_cuentas(self._sesion, cuenta_medica_ids, TipoTransicion.RECHAZO_LOTE)
        elif estado_receptor == "ACEPTADO":
            # T-06 (Seccion 5.2.4): "Inicio de la auditoria... al
            # aceptarse el lote". Se devuelven igual que en el rechazo,
            # para que MonitorearRespuestaIafas pueda registrar el
            # evento propio de cada cuenta (RF-16/RT-01: un evento por
            # cada transicion DE LA CUENTA, no solo del lote).
            cuenta_medica_ids = await self._cuentas_del_lote(lote_id)
            await transicionar_cuentas(
                self._sesion, cuenta_medica_ids, TipoTransicion.INICIO_AUDITORIA
            )

        await self._sesion.flush()
        acuse_id = acuse.id
        await self._sesion.commit()
        return acuse_id, cuenta_medica_ids
