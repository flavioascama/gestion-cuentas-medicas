"""Adaptador de RepositorioCorreos."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.dominio.comunicaciones.correos import (
    LONGITUD_MAXIMA_ASUNTO,
    LONGITUD_MAXIMA_TEXTO,
    AdjuntoRegistrado,
    ContenidoAdjunto,
    CorreoPorRegistrar,
    CorreoRegistrado,
    RepositorioCorreos,
    Resolucion,
)
from app.infraestructura.persistencia.modelos_correos import (
    AdjuntoCorreoIafasModelo,
    CorreoIafasModelo,
)
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, IafasModelo


def _a_registrado(
    fila: CorreoIafasModelo, identificacion: str | None, cantidad_adjuntos: int
) -> CorreoRegistrado:
    return CorreoRegistrado(
        id=fila.id,
        remitente=fila.remitente,
        codigo_iafas=fila.codigo_iafas,
        asunto=fila.asunto,
        fecha=fila.fecha_correo,
        recibido_en=fila.recibido_en,
        estado=fila.estado,
        motivo_revision=fila.motivo_revision,
        comunicacion_codigo=fila.comunicacion_codigo,
        cuenta_medica_id=fila.cuenta_medica_id,
        identificacion_interna=identificacion,
        huella=fila.huella_sha256,
        resuelto_por=fila.resuelto_por,
        resuelto_en=fila.resuelto_en,
        nota_resolucion=fila.nota_resolucion,
        cantidad_adjuntos=cantidad_adjuntos,
    )


class RepositorioCorreosSql(RepositorioCorreos):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ya_registrado(self, huella: str) -> bool:
        encontrado = await self._sesion.scalar(
            sa.select(sa.literal(True)).where(CorreoIafasModelo.huella_sha256 == huella)
        )
        return bool(encontrado)

    async def remitentes_por_iafas(self) -> dict[str, str]:
        filas = await self._sesion.execute(
            sa.select(IafasModelo.codigo, IafasModelo.correo_remitente).where(
                IafasModelo.correo_remitente.is_not(None)
            )
        )
        return {codigo: remitente for codigo, remitente in filas.all() if remitente}

    async def registrar(self, correo: CorreoPorRegistrar, recibido_en: datetime) -> int:
        recibido = correo.correo
        fila = CorreoIafasModelo(
            huella_sha256=recibido.huella,
            remitente=recibido.remitente[:200],
            codigo_iafas=correo.codigo_iafas,
            asunto=recibido.asunto[:LONGITUD_MAXIMA_ASUNTO],
            texto=recibido.texto[:LONGITUD_MAXIMA_TEXTO],
            fecha_correo=recibido.fecha,
            recibido_en=recibido_en,
            estado=correo.estado.value,
            motivo_revision=correo.motivo_revision.value if correo.motivo_revision else None,
            comunicacion_codigo=correo.comunicacion_codigo,
            cuenta_medica_id=correo.cuenta_medica_id,
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        for adjunto in correo.adjuntos:
            self._sesion.add(
                AdjuntoCorreoIafasModelo(
                    correo_id=fila.id,
                    nombre=adjunto.nombre,
                    tipo=adjunto.tipo,
                    tamano=adjunto.tamano,
                    huella_sha256=adjunto.huella,
                    motivo_omision=adjunto.motivo_omision.value if adjunto.motivo_omision else None,
                    contenido=adjunto.contenido,
                )
            )
        await self._sesion.commit()
        return fila.id

    async def _identificacion(self, cuenta_id: int | None) -> str | None:
        if cuenta_id is None:
            return None
        valor = await self._sesion.scalar(
            sa.select(CuentaMedicaModelo.identificacion_interna).where(
                CuentaMedicaModelo.id == cuenta_id
            )
        )
        return str(valor) if valor is not None else None

    async def obtener(self, correo_id: int) -> CorreoRegistrado | None:
        fila = await self._sesion.get(CorreoIafasModelo, correo_id, populate_existing=True)
        if fila is None:
            return None
        adjuntos = (
            await self._sesion.execute(
                sa.select(AdjuntoCorreoIafasModelo)
                .options(defer(AdjuntoCorreoIafasModelo.contenido))
                .where(AdjuntoCorreoIafasModelo.correo_id == correo_id)
                .order_by(AdjuntoCorreoIafasModelo.id)
            )
        ).scalars()
        registrados = tuple(
            AdjuntoRegistrado(
                id=adjunto.id,
                nombre=adjunto.nombre,
                tipo=adjunto.tipo,
                tamano=adjunto.tamano,
                huella=adjunto.huella_sha256,
                almacenado=adjunto.motivo_omision is None,
                motivo_omision=adjunto.motivo_omision,
            )
            for adjunto in adjuntos.all()
        )
        base = _a_registrado(
            fila, await self._identificacion(fila.cuenta_medica_id), len(registrados)
        )
        return replace(base, texto=fila.texto, adjuntos=registrados)

    async def listar(
        self, estado: str | None, cuenta_medica_id: int | None, limite: int = 200
    ) -> list[CorreoRegistrado]:
        cantidad = (
            sa.select(sa.func.count(AdjuntoCorreoIafasModelo.id))
            .where(AdjuntoCorreoIafasModelo.correo_id == CorreoIafasModelo.id)
            .correlate(CorreoIafasModelo)
            .scalar_subquery()
        )
        consulta = (
            sa.select(CorreoIafasModelo, CuentaMedicaModelo.identificacion_interna, cantidad)
            .outerjoin(
                CuentaMedicaModelo, CuentaMedicaModelo.id == CorreoIafasModelo.cuenta_medica_id
            )
            .options(defer(CorreoIafasModelo.texto))
        )
        if estado is not None:
            consulta = consulta.where(CorreoIafasModelo.estado == estado)
        if cuenta_medica_id is not None:
            consulta = consulta.where(CorreoIafasModelo.cuenta_medica_id == cuenta_medica_id)
        filas = await self._sesion.execute(
            consulta.order_by(CorreoIafasModelo.id.desc()).limit(limite)
        )
        return [
            _a_registrado(fila, identificacion, int(adjuntos or 0))
            for fila, identificacion, adjuntos in filas.all()
        ]

    async def contenido_adjunto(self, correo_id: int, adjunto_id: int) -> ContenidoAdjunto | None:
        fila = await self._sesion.scalar(
            sa.select(AdjuntoCorreoIafasModelo).where(
                AdjuntoCorreoIafasModelo.id == adjunto_id,
                AdjuntoCorreoIafasModelo.correo_id == correo_id,
            )
        )
        if fila is None or fila.contenido is None:
            return None
        return ContenidoAdjunto(
            nombre=fila.nombre, tipo=fila.tipo, huella=fila.huella_sha256, contenido=fila.contenido
        )

    async def resolver(self, correo_id: int, resolucion: Resolucion) -> None:
        await self._sesion.execute(
            sa.update(CorreoIafasModelo)
            .where(CorreoIafasModelo.id == correo_id)
            .values(
                estado=resolucion.estado.value,
                cuenta_medica_id=resolucion.cuenta_medica_id,
                resuelto_por=resolucion.usuario[:60],
                resuelto_en=resolucion.instante,
                nota_resolucion=resolucion.nota,
                motivo_revision=None,
            )
        )
        await self._sesion.flush()

    async def cuenta_por_identificacion(self, identificacion_interna: str) -> int | None:
        cuenta_id = await self._sesion.scalar(
            sa.select(CuentaMedicaModelo.id).where(
                CuentaMedicaModelo.identificacion_interna == identificacion_interna
            )
        )
        return int(cuenta_id) if cuenta_id is not None else None
