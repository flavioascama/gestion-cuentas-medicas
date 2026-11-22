"""Adaptador de RepositorioAvisos: lee el almacen de eventos (solo
lectura) y resuelve la cuenta o el lote al que pertenece cada aviso. Los
avisos TRABAJO_AGOTADO (RNF-20) salen de la cola de trabajos."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.avisos.destinatarios import es_aviso_de_observacion
from app.dominio.avisos.puertos import RepositorioAvisos
from app.dominio.avisos.valores import (
    TIPO_AVISO_CORREO_POR_REVISAR,
    TIPO_AVISO_TRABAJO_AGOTADO,
    TIPOS_AVISO_MARCABLES,
    EventoAviso,
)
from app.dominio.contingencia.valores import es_no_encontrado_legado
from app.dominio.puertos_comunes import TIPO_AGREGADO_LOTE
from app.infraestructura.persistencia.atencion_avisos_sql import EvaluadorAtencionAvisos
from app.infraestructura.persistencia.modelos_correos import CorreoIafasModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    EventoModelo,
    LoteFacturacionModelo,
    TrabajoModelo,
)
from app.infraestructura.persistencia.modelos_observaciones import ObservacionModelo


def _observacion_de(carga: dict[str, Any]) -> dict[str, Any]:
    # La entrega de una respuesta sigue a la observacion (destinatarios.py).
    observacion_id = carga.get("observacion_id")
    return {} if observacion_id is None else {"observacion_id": observacion_id}


class RepositorioAvisosSql(RepositorioAvisos):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(self, tipos_evento: list[str], limite: int) -> list[EventoAviso]:
        avisos = await self._avisos_de_eventos(tipos_evento, limite)
        if TIPO_AVISO_TRABAJO_AGOTADO in tipos_evento:
            avisos.extend(await self._trabajos_agotados(limite))
        if TIPO_AVISO_CORREO_POR_REVISAR in tipos_evento:
            avisos.extend(await self._correos_por_revisar(limite))
        avisos.sort(key=lambda aviso: aviso.ocurrido_en, reverse=True)
        return await self._con_responsables(avisos[:limite])

    async def _con_responsables(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        """A quien sigue cada aviso de observacion: la reasignacion, al
        responsable que fijo; los demas, al responsable actual."""
        ids = {
            int(a.datos["observacion_id"])
            for a in avisos
            if es_aviso_de_observacion(a) and a.datos.get("observacion_id") is not None
        }
        if not ids:
            return avisos
        filas = await self._sesion.execute(
            sa.select(
                ObservacionModelo.id,
                ObservacionModelo.responsable_usuario_id,
                ObservacionModelo.responsable_rol,
            ).where(ObservacionModelo.id.in_(ids))
        )
        actuales = {fila[0]: (fila[1], fila[2]) for fila in filas.all()}
        resultado = []
        for aviso in avisos:
            observacion_id = aviso.datos.get("observacion_id")
            if not es_aviso_de_observacion(aviso) or observacion_id is None:
                resultado.append(aviso)
                continue
            usuario, rol = actuales.get(int(observacion_id), (None, None))
            if aviso.tipo_evento == "OBSERVACION_REASIGNADA":
                usuario = aviso.datos.get("responsable_usuario_id")
                rol = aviso.datos.get("responsable_rol", rol)
            resultado.append(replace(aviso, responsable_usuario_id=usuario, responsable_rol=rol))
        return resultado

    async def obtener(self, evento_id: str) -> EventoAviso | None:
        try:
            identificador = uuid.UUID(evento_id)
        except ValueError:
            return None  # los avisos de la cola y del buzon no son eventos
        eventos = await self._avisos_de_eventos(
            list(TIPOS_AVISO_MARCABLES), 1, EventoModelo.evento_id == identificador
        )
        return eventos[0] if eventos else None

    async def evaluar_atencion(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        return await EvaluadorAtencionAvisos(self._sesion).evaluar(avisos)

    async def _correos_por_revisar(self, limite: int) -> list[EventoAviso]:
        filas = await self._sesion.execute(
            sa.select(
                CorreoIafasModelo.id,
                CorreoIafasModelo.recibido_en,
                CorreoIafasModelo.remitente,
                CorreoIafasModelo.motivo_revision,
                CorreoIafasModelo.codigo_iafas,
            )
            .where(CorreoIafasModelo.estado == "POR_REVISAR")
            .order_by(CorreoIafasModelo.recibido_en.desc())
            .limit(limite)
        )
        return [
            EventoAviso(
                evento_id=f"correo-{fila[0]}",
                tipo_evento=TIPO_AVISO_CORREO_POR_REVISAR,
                ocurrido_en=fila[1],
                datos={
                    "correo_id": fila[0],
                    "remitente": fila[2],
                    "motivo": fila[3],
                    "iafas": fila[4],
                },
                cuenta_medica_id=None,
                identificacion_interna=None,
                lote_id=None,
                numero_lote=None,
            )
            for fila in filas.all()
        ]

    async def _trabajos_agotados(self, limite: int) -> list[EventoAviso]:
        trabajos = (
            (
                await self._sesion.execute(
                    sa.select(TrabajoModelo)
                    .where(TrabajoModelo.estado == "AGOTADO")
                    .order_by(TrabajoModelo.actualizado_en.desc())
                    .limit(limite)
                )
            )
            .scalars()
            .all()
        )
        # Un asegurado no encontrado no es una falla del proceso (RNF-20):
        # los trabajos anteriores al estado SIN_RESULTADO quedaron AGOTADO
        # con el texto del robot, y no se avisan como falla.
        trabajos = [t for t in trabajos if not es_no_encontrado_legado(t.error)]
        cuentas = await self._identificaciones(
            {
                int(t.carga_util["cuenta_medica_id"])
                for t in trabajos
                if "cuenta_medica_id" in t.carga_util
            }
        )
        lotes = await self._numeros_lote(
            {int(t.carga_util["lote_id"]) for t in trabajos if "lote_id" in t.carga_util}
        )
        resultado: list[EventoAviso] = []
        for trabajo in trabajos:
            cuenta_id = trabajo.carga_util.get("cuenta_medica_id")
            lote_id = trabajo.carga_util.get("lote_id")
            resultado.append(
                EventoAviso(
                    evento_id=f"trabajo-{trabajo.id}",
                    tipo_evento=TIPO_AVISO_TRABAJO_AGOTADO,
                    ocurrido_en=trabajo.actualizado_en,
                    datos={
                        "tipo_trabajo": trabajo.tipo,
                        "intentos": trabajo.intentos,
                        "error": (trabajo.error or "")[:200],
                        "plataforma": trabajo.carga_util.get("plataforma"),
                        **_observacion_de(trabajo.carga_util),
                    },
                    cuenta_medica_id=int(cuenta_id) if cuenta_id is not None else None,
                    identificacion_interna=cuentas.get(int(cuenta_id)) if cuenta_id else None,
                    lote_id=int(lote_id) if lote_id is not None else None,
                    numero_lote=lotes.get(int(lote_id)) if lote_id else None,
                )
            )
        return resultado

    async def _identificaciones(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        filas = await self._sesion.execute(
            sa.select(CuentaMedicaModelo.id, CuentaMedicaModelo.identificacion_interna).where(
                CuentaMedicaModelo.id.in_(ids)
            )
        )
        return {fila[0]: fila[1] for fila in filas.all()}

    async def _numeros_lote(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        filas = await self._sesion.execute(
            sa.select(LoteFacturacionModelo.id, LoteFacturacionModelo.numero).where(
                LoteFacturacionModelo.id.in_(ids)
            )
        )
        return {fila[0]: fila[1] for fila in filas.all()}

    async def _avisos_de_eventos(
        self, tipos_evento: list[str], limite: int, *condiciones: Any
    ) -> list[EventoAviso]:
        es_lote = EventoModelo.tipo_agregado == TIPO_AGREGADO_LOTE
        filas = (
            await self._sesion.execute(
                sa.select(
                    EventoModelo.evento_id,
                    EventoModelo.tipo_evento,
                    EventoModelo.ocurrido_en,
                    EventoModelo.datos,
                    EventoModelo.cuenta_medica_id,
                    CuentaMedicaModelo.identificacion_interna,
                    sa.case((es_lote, EventoModelo.agregado_id), else_=None),
                    LoteFacturacionModelo.numero,
                    EventoModelo.actor,
                )
                .outerjoin(
                    CuentaMedicaModelo, CuentaMedicaModelo.id == EventoModelo.cuenta_medica_id
                )
                .outerjoin(
                    LoteFacturacionModelo,
                    sa.and_(es_lote, LoteFacturacionModelo.id == EventoModelo.agregado_id),
                )
                .where(EventoModelo.tipo_evento.in_(tipos_evento), *condiciones)
                .order_by(EventoModelo.ocurrido_en.desc())
                .limit(limite)
            )
        ).all()
        return [
            EventoAviso(
                evento_id=str(fila[0]),
                tipo_evento=fila[1],
                ocurrido_en=fila[2],
                datos=fila[3] or {},
                cuenta_medica_id=fila[4],
                identificacion_interna=fila[5],
                lote_id=fila[6],
                numero_lote=fila[7],
                actor=fila[8],
            )
            for fila in filas
        ]
