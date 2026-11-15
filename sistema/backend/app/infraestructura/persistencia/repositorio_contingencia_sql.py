"""Adaptador de RepositorioContingencia: la disponibilidad se lee de la cola
de trabajos (la ultima solicitud agoto sus reintentos) y los registros, de
los eventos (registro + revision posterior, sin tabla mutable)."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.contingencia.puertos import RepositorioContingencia
from app.dominio.contingencia.valores import (
    TIPO_EVENTO_COBERTURA_CONTINGENCIA,
    TIPO_EVENTO_REVISION_CONTINGENCIA,
    TIPO_EVENTO_VALIDACION_CONTINGENCIA,
    EstadoRevision,
    RegistroContingencia,
    ResumenTrabajo,
    TipoOperacion,
)
from app.dominio.puertos_comunes import TIPO_AGREGADO_LOTE
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    EventoModelo,
    LoteFacturacionModelo,
    TrabajoModelo,
)

_TIPO_OPERACION = {
    TIPO_EVENTO_COBERTURA_CONTINGENCIA: TipoOperacion.COBERTURA,
    TIPO_EVENTO_VALIDACION_CONTINGENCIA: TipoOperacion.VALIDACION,
}


def _resumen(tipo: TipoOperacion, datos: dict[str, Any]) -> str:
    if tipo is TipoOperacion.COBERTURA:
        return (
            f"Cobertura {datos.get('condicion_cobertura', '—')}, "
            f"autorización {datos.get('codigo_autorizacion', '—')}"
        )
    if datos.get("resultado") == "VALIDADO":
        return f"Lote validado, archivo {datos.get('nombre_s01', '—')}"
    return "Lote observado por el validador"


class RepositorioContingenciaSql(RepositorioContingencia):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ultimo_trabajo(
        self, tipo_trabajo: str, clave: str, valor: int
    ) -> ResumenTrabajo | None:
        trabajo = (
            await self._sesion.execute(
                sa.select(TrabajoModelo)
                .where(
                    TrabajoModelo.tipo == tipo_trabajo,
                    TrabajoModelo.carga_util[clave].as_integer() == valor,
                )
                .order_by(TrabajoModelo.creado_en.desc(), TrabajoModelo.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if trabajo is None:
            return None
        return ResumenTrabajo(
            estado=trabajo.estado,
            error=trabajo.error,
            intentos=trabajo.intentos,
            creado_en=trabajo.creado_en,
            actualizado_en=trabajo.actualizado_en,
        )

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        return (
            await self._sesion.execute(
                sa.select(LoteFacturacionModelo.estado).where(LoteFacturacionModelo.id == lote_id)
            )
        ).scalar_one_or_none()

    async def marcar_lote_observado(self, lote_id: int) -> None:
        await self._sesion.execute(
            sa.update(LoteFacturacionModelo)
            .where(LoteFacturacionModelo.id == lote_id)
            .values(estado="OBSERVADO_VALIDADOR")
        )

    async def listar_registros(self) -> list[RegistroContingencia]:
        es_lote = EventoModelo.tipo_agregado == TIPO_AGREGADO_LOTE
        filas = (
            await self._sesion.execute(
                sa.select(
                    EventoModelo.evento_id,
                    EventoModelo.tipo_evento,
                    EventoModelo.cuenta_medica_id,
                    CuentaMedicaModelo.identificacion_interna,
                    sa.case((es_lote, EventoModelo.agregado_id), else_=None),
                    LoteFacturacionModelo.numero,
                    EventoModelo.datos,
                    EventoModelo.actor,
                    EventoModelo.ocurrido_en,
                )
                .outerjoin(
                    CuentaMedicaModelo, CuentaMedicaModelo.id == EventoModelo.cuenta_medica_id
                )
                .outerjoin(
                    LoteFacturacionModelo,
                    sa.and_(es_lote, LoteFacturacionModelo.id == EventoModelo.agregado_id),
                )
                .where(
                    EventoModelo.tipo_evento.in_(
                        [*_TIPO_OPERACION, TIPO_EVENTO_REVISION_CONTINGENCIA]
                    )
                )
                .order_by(EventoModelo.ocurrido_en.desc())
            )
        ).all()
        revisiones = {
            str((fila[6] or {}).get("registro_evento_id")): fila
            for fila in filas
            if fila[1] == TIPO_EVENTO_REVISION_CONTINGENCIA
        }
        return [
            self._a_registro(fila, revisiones.get(str(fila[0])))
            for fila in filas
            if fila[1] in _TIPO_OPERACION
        ]

    @staticmethod
    def _a_registro(fila: Any, revision: Any | None) -> RegistroContingencia:
        tipo = _TIPO_OPERACION[fila[1]]
        datos: dict[str, Any] = fila[6] or {}
        estado = EstadoRevision.PENDIENTE
        if revision is not None:
            conforme = bool((revision[6] or {}).get("conforme"))
            estado = EstadoRevision.CONFORME if conforme else EstadoRevision.NO_CONFORME
        return RegistroContingencia(
            evento_id=str(fila[0]),
            tipo_operacion=tipo,
            cuenta_medica_id=fila[2],
            identificacion_interna=fila[3],
            lote_id=fila[4],
            numero_lote=fila[5],
            resumen=_resumen(tipo, datos),
            sustento=str(datos.get("sustento", "")),
            registrado_por=fila[7],
            registrado_en=fila[8],
            estado_revision=estado,
            revisado_por=revision[7] if revision is not None else None,
            revisado_en=revision[8] if revision is not None else None,
            comentario_revision=(
                str((revision[6] or {}).get("comentario")) if revision is not None else None
            ),
        )
