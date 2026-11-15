"""Adaptador de RepositorioComunicaciones."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.comunicaciones.casos_uso import (
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
    Aplicacion,
    ComunicacionRegistrada,
    RepositorioComunicaciones,
)
from app.infraestructura.persistencia.modelos_comunicaciones import ComunicacionIafasModelo
from app.infraestructura.persistencia.modelos_documentos_pago import (
    ComprobanteReemplazadoModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    DocumentoFacturadorModelo,
    IpressModelo,
    TrabajoModelo,
)


def _a_registrada(fila: ComunicacionIafasModelo) -> ComunicacionRegistrada:
    return ComunicacionRegistrada(
        codigo=fila.codigo,
        canal=fila.canal,
        tipo=fila.tipo,
        codigo_iafas=fila.codigo_iafas,
        codigo_ipress=fila.codigo_ipress,
        documento=fila.documento,
        datos=dict(fila.datos),
        emitida_en=fila.emitida_en,
        cuenta_medica_id=fila.cuenta_medica_id,
        resultado=fila.resultado,
        detalle=fila.detalle,
        observacion_id=fila.observacion_id,
        recibida_en=fila.recibida_en,
        respuesta_remitida_en=fila.respuesta_remitida_en,
    )


class RepositorioComunicacionesSql(RepositorioComunicaciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ya_registrada(self, codigo: str) -> bool:
        encontrada = await self._sesion.scalar(
            sa.select(sa.literal(True)).where(ComunicacionIafasModelo.codigo == codigo)
        )
        return bool(encontrada)

    async def registrar(self, aplicacion: Aplicacion, recibida_en: datetime) -> None:
        comunicacion = aplicacion.comunicacion
        self._sesion.add(
            ComunicacionIafasModelo(
                codigo=comunicacion.codigo,
                canal=comunicacion.canal,
                tipo=comunicacion.tipo,
                codigo_iafas=comunicacion.codigo_iafas,
                codigo_ipress=comunicacion.codigo_ipress,
                documento=comunicacion.documento,
                datos=comunicacion.datos,
                emitida_en=comunicacion.emitida_en,
                cuenta_medica_id=aplicacion.cuenta_medica_id,
                resultado=aplicacion.resultado.value,
                detalle=(aplicacion.detalle or None) and aplicacion.detalle[:500],
                observacion_id=aplicacion.observacion_id,
                recibida_en=recibida_en,
            )
        )
        await self._sesion.commit()

    async def descartar_cambios_pendientes(self) -> None:
        await self._sesion.rollback()

    async def codigos_ipress(self) -> list[str]:
        filas = await self._sesion.scalars(
            sa.select(IpressModelo.codigo_ipress).order_by(IpressModelo.codigo_ipress)
        )
        return list(filas.all())

    async def obtener(self, codigo: str) -> ComunicacionRegistrada | None:
        fila = await self._sesion.scalar(
            sa.select(ComunicacionIafasModelo).where(ComunicacionIafasModelo.codigo == codigo)
        )
        return _a_registrada(fila) if fila is not None else None

    async def revision_pendiente(self) -> int | None:
        pendiente = await self._sesion.scalar(
            sa.select(TrabajoModelo.id)
            .where(
                TrabajoModelo.tipo == TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
                TrabajoModelo.estado.in_(("PENDIENTE", "EN_PROCESO")),
            )
            .order_by(TrabajoModelo.id)
            .limit(1)
        )
        return int(pendiente) if pendiente is not None else None

    async def cuenta_de_documento(self, documento: str) -> int | None:
        numero = DocumentoFacturadorModelo.serie + DocumentoFacturadorModelo.numero
        vigente = await self._sesion.scalar(
            sa.select(DocumentoFacturadorModelo.cuenta_id).where(numero == documento).limit(1)
        )
        if vigente is not None:
            return int(vigente)
        reemplazado = await self._sesion.scalar(
            sa.select(DocumentoFacturadorModelo.cuenta_id)
            .join(
                ComprobanteReemplazadoModelo,
                ComprobanteReemplazadoModelo.documento_facturador_id
                == DocumentoFacturadorModelo.id,
            )
            .where(
                ComprobanteReemplazadoModelo.serie + ComprobanteReemplazadoModelo.numero
                == documento
            )
            .limit(1)
        )
        return int(reemplazado) if reemplazado is not None else None

    async def origen_de_observacion(self, observacion_id: int) -> ComunicacionRegistrada | None:
        fila = await self._sesion.scalar(
            sa.select(ComunicacionIafasModelo)
            .where(ComunicacionIafasModelo.observacion_id == observacion_id)
            .limit(1)
        )
        return _a_registrada(fila) if fila is not None else None

    async def marcar_respuesta_remitida(self, codigo: str, instante: datetime) -> None:
        await self._sesion.execute(
            sa.update(ComunicacionIafasModelo)
            .where(ComunicacionIafasModelo.codigo == codigo)
            .values(respuesta_remitida_en=instante)
        )
        await self._sesion.commit()

    async def listar(
        self, cuenta_medica_id: int | None = None, limite: int = 200
    ) -> list[ComunicacionRegistrada]:
        consulta = sa.select(ComunicacionIafasModelo)
        if cuenta_medica_id is not None:
            consulta = consulta.where(ComunicacionIafasModelo.cuenta_medica_id == cuenta_medica_id)
        filas = await self._sesion.execute(
            consulta.order_by(ComunicacionIafasModelo.id.desc()).limit(limite)
        )
        return [_a_registrada(fila) for fila in filas.scalars().all()]
