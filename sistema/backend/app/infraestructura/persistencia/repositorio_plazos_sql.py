"""Adaptador de RepositorioPlazos (Seccion 5.2.4.3, Tabla 61, Fase 27).

Cada metodo resuelve, con SQL portable entre SQLite y Postgres, tres
cosas por fila: el plazo que corresponde (columna de `iafas` o parametro
del sistema, recibido por el constructor), el instante desde el que el
hito esta abierto, y si ya existe un aviso o un escalamiento para la
ocurrencia VIGENTE de ese hito. Como a lo sumo una observacion por
cuenta esta ABIERTA a la vez (el motor rechaza una segunda GLOSA sobre
una cuenta ya GLOSADA), y los hitos 2 a 4 se definen sobre el estado
ACTUAL de la cuenta, filtrar el evento de aviso/escalamiento por
`cuenta_medica_id` y por `ocurrido_en >= <inicio del hito>` basta para
no confundirlo con una ocurrencia anterior del mismo tipo de hito sobre
la misma cuenta -- no hace falta inspeccionar el payload JSON del
evento."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.dominio.plazos.puertos import RepositorioPlazos
from app.dominio.plazos.valores import (
    CuentaConPlazo,
    CuentaConVigenciaCartaGarantia,
    ObservacionConPlazo,
)
from app.infraestructura.persistencia.modelos_carta_garantia import CartaGarantiaModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    EventoModelo,
    IafasModelo,
)
from app.infraestructura.persistencia.modelos_observaciones import ObservacionModelo
from app.infraestructura.persistencia.repositorio_conformidad_auditoria_sql import (
    conformidad_desde,
)


def _ya_existe_evento(cuenta_id_col: Any, desde_col: Any, tipo_evento: str) -> ColumnElement[bool]:
    evento = aliased(EventoModelo)
    return (
        sa.select(sa.literal(1))
        .where(
            evento.cuenta_medica_id == cuenta_id_col,
            evento.tipo_evento == tipo_evento,
            evento.ocurrido_en >= desde_col,
        )
        .exists()
    )


def _hito_desde_por_estado_actual() -> ColumnElement[Any]:
    """Instante en que la cuenta entro a su estado ACTUAL: el ultimo
    evento de esa cuenta cuyo estado_nuevo coincide con `estado`."""

    evento = aliased(EventoModelo)
    return (
        sa.select(sa.func.max(evento.ocurrido_en))
        .where(
            evento.cuenta_medica_id == CuentaMedicaModelo.id,
            evento.estado_nuevo == CuentaMedicaModelo.estado,
        )
        .scalar_subquery()
    )


class RepositorioPlazosSql(RepositorioPlazos):
    def __init__(self, sesion: AsyncSession, dias_plazo_reenvio_lote_rechazado: int) -> None:
        self._sesion = sesion
        self._dias_plazo_reenvio_lote_rechazado = dias_plazo_reenvio_lote_rechazado

    async def observaciones_abiertas(self) -> list[ObservacionConPlazo]:
        filas = (
            await self._sesion.execute(
                sa.select(
                    ObservacionModelo.id,
                    ObservacionModelo.cuenta_medica_id,
                    IafasModelo.dias_plazo_respuesta_observacion,
                    ObservacionModelo.registrado_en,
                    _ya_existe_evento(
                        ObservacionModelo.cuenta_medica_id,
                        ObservacionModelo.registrado_en,
                        "OBSERVACION_PLAZO_PROXIMO_A_VENCER",
                    ),
                    _ya_existe_evento(
                        ObservacionModelo.cuenta_medica_id,
                        ObservacionModelo.registrado_en,
                        "OBSERVACION_PLAZO_VENCIDO_ESCALADO",
                    ),
                )
                .join(
                    CuentaMedicaModelo, CuentaMedicaModelo.id == ObservacionModelo.cuenta_medica_id
                )
                .join(IafasModelo, IafasModelo.id == CuentaMedicaModelo.iafas_id)
                .where(ObservacionModelo.estado == "ABIERTA")
            )
        ).all()
        return [
            ObservacionConPlazo(
                observacion_id=fila[0],
                cuenta_medica_id=fila[1],
                plazo_dias=fila[2],
                abierta_desde=fila[3],
                ya_avisada=bool(fila[4]),
                ya_escalada=bool(fila[5]),
            )
            for fila in filas
        ]

    async def cuentas_rechazadas(self) -> list[CuentaConPlazo]:
        return await self._cuentas_con_plazo(
            estado="RECHAZADA",
            plazo_dias=self._dias_plazo_reenvio_lote_rechazado,
            tipo_evento_aviso="LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER",
            tipo_evento_escalado="LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO",
        )

    async def cuentas_en_auditoria(self) -> list[CuentaConPlazo]:
        return await self._cuentas_con_plazo(
            estado="EN_AUDITORIA",
            plazo_dias=IafasModelo.dias_plazo_comunicacion_auditoria,
            tipo_evento_aviso="AUDITORIA_PLAZO_PROXIMO_A_VENCER",
            tipo_evento_escalado="AUDITORIA_EXCEDIDA",
            # CU-07: con la conformidad registrada, el resultado ya se
            # comunico y el plazo deja de correr.
            sin_conformidad=True,
        )

    async def cuentas_liquidadas(self) -> list[CuentaConPlazo]:
        return await self._cuentas_con_plazo(
            estado=("LIQUIDADA", "LIQUIDADA_PARCIAL"),
            plazo_dias=IafasModelo.dias_plazo_pago_liquidacion,
            tipo_evento_aviso="LIQUIDACION_PAGO_PROXIMO_A_VENCER",
            tipo_evento_escalado="LIQUIDACION_PAGO_VENCIDO_ESCALADO",
        )

    async def _cuentas_con_plazo(
        self,
        *,
        estado: str | tuple[str, ...],
        plazo_dias: int | Any,
        tipo_evento_aviso: str,
        tipo_evento_escalado: str,
        sin_conformidad: bool = False,
    ) -> list[CuentaConPlazo]:
        hito_desde = _hito_desde_por_estado_actual()
        condicion_estado = (
            CuentaMedicaModelo.estado == estado
            if isinstance(estado, str)
            else CuentaMedicaModelo.estado.in_(estado)
        )
        columna_plazo = sa.literal(plazo_dias) if isinstance(plazo_dias, int) else plazo_dias
        consulta = sa.select(
            CuentaMedicaModelo.id,
            columna_plazo,
            hito_desde,
            _ya_existe_evento(CuentaMedicaModelo.id, hito_desde, tipo_evento_aviso),
            _ya_existe_evento(CuentaMedicaModelo.id, hito_desde, tipo_evento_escalado),
        ).where(condicion_estado)
        if sin_conformidad:
            consulta = consulta.where(~conformidad_desde(CuentaMedicaModelo.id, hito_desde))
        if not isinstance(plazo_dias, int):
            consulta = consulta.join(IafasModelo, IafasModelo.id == CuentaMedicaModelo.iafas_id)
        filas = (await self._sesion.execute(consulta)).all()
        return [
            CuentaConPlazo(
                cuenta_medica_id=fila[0],
                plazo_dias=fila[1],
                hito_desde=fila[2],
                ya_avisada=bool(fila[3]),
                ya_escalada=bool(fila[4]),
            )
            for fila in filas
            # `hito_desde` solo falta cuando el estado de la cuenta se
            # fijo sin pasar por un evento (dato anomalo, nunca el
            # resultado del flujo normal: toda transicion real emite su
            # evento, Fase 24/25) -- sin un origen no hay como calcular
            # el vencimiento del hito, se omite en vez de reventar.
            if fila[2] is not None
        ]

    async def cuentas_con_carta_garantia_por_vencer(
        self,
    ) -> list[CuentaConVigenciaCartaGarantia]:
        # RF-13: la vigencia de la carta de garantia registrada; sin carta,
        # la de la acreditacion (sustituto anterior a la entidad).
        vigente_hasta = sa.func.coalesce(
            CartaGarantiaModelo.vigente_hasta, AcreditacionModelo.vigente_hasta
        )
        desde = sa.func.coalesce(CartaGarantiaModelo.registrado_en, AcreditacionModelo.instante)
        filas = (
            await self._sesion.execute(
                sa.select(
                    CuentaMedicaModelo.id,
                    vigente_hasta,
                    _ya_existe_evento(
                        CuentaMedicaModelo.id, desde, "CARTA_GARANTIA_PROXIMA_A_VENCER"
                    ),
                )
                .outerjoin(
                    AcreditacionModelo, AcreditacionModelo.cuenta_id == CuentaMedicaModelo.id
                )
                .outerjoin(
                    CartaGarantiaModelo,
                    CartaGarantiaModelo.cuenta_medica_id == CuentaMedicaModelo.id,
                )
                .where(
                    CuentaMedicaModelo.estado.in_(("REGISTRADA", "FACTURADA")),
                    vigente_hasta.is_not(None),
                )
            )
        ).all()
        return [
            CuentaConVigenciaCartaGarantia(
                cuenta_medica_id=fila[0],
                vigente_hasta=fila[1],
                ya_avisada=bool(fila[2]),
            )
            for fila in filas
        ]
