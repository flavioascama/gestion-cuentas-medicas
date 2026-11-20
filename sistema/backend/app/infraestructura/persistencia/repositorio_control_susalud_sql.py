"""Adaptador de RepositorioControlSusalud (RT-05, RI-16).

Sujeto a envio: todo lote del periodo salvo el observado por el validador
(se corrige generando otro lote; el observado no se remite). El envio se
lee de `lote_facturacion.enviado_susalud_en`, que fija EnviarLoteSusalud."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.dominio.plazos.susalud import (
    TIPO_AVISO_SUSALUD,
    TIPO_ESCALADO_SUSALUD,
    LotePendienteSusalud,
    LotesPeriodo,
    RepositorioControlSusalud,
)
from app.infraestructura.persistencia.modelos_declaracion_susalud import (
    DeclaracionSusaludSinFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    EventoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    ESTADOS_ENVIABLES_SUSALUD,
)

_NO_SUJETOS_A_ENVIO = ("OBSERVADO_VALIDADOR",)


def _ya_registrado(tipo_evento: str) -> sa.ColumnElement[bool]:
    evento = aliased(EventoModelo)
    return (
        sa.select(sa.literal(1))
        .where(
            evento.tipo_agregado == "LOTE",
            evento.agregado_id == LoteFacturacionModelo.id,
            evento.tipo_evento == tipo_evento,
        )
        .exists()
    )


class RepositorioControlSusaludSql(RepositorioControlSusalud):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def lotes_por_periodo(self) -> list[LotesPeriodo]:
        sin_enviar = LoteFacturacionModelo.enviado_susalud_en.is_(None)
        estado = LoteFacturacionModelo.estado
        pendiente = sa.and_(sin_enviar, estado.not_in(_NO_SUJETOS_A_ENVIO))
        # Mismo criterio con que SolicitarEnvioSusalud elige los lotes.
        listo = sa.and_(sin_enviar, estado.in_(ESTADOS_ENVIABLES_SUSALUD))
        filas = (
            await self._sesion.execute(
                sa.select(
                    LoteFacturacionModelo.periodo,
                    sa.func.count(LoteFacturacionModelo.id),
                    sa.func.sum(sa.case((pendiente, 1), else_=0)),
                    sa.func.max(LoteFacturacionModelo.enviado_susalud_en),
                    sa.func.sum(sa.case((listo, 1), else_=0)),
                ).group_by(LoteFacturacionModelo.periodo)
            )
        ).all()
        return [
            LotesPeriodo(
                periodo=periodo,
                lotes=int(lotes),
                pendientes_envio=int(pendientes or 0),
                ultimo_envio=ultimo_envio,
                listos_envio=int(listos or 0),
            )
            for periodo, lotes, pendientes, ultimo_envio, listos in filas
        ]

    async def lotes_pendientes_envio(self) -> list[LotePendienteSusalud]:
        filas = (
            await self._sesion.execute(
                sa.select(
                    LoteFacturacionModelo.id,
                    LoteFacturacionModelo.periodo,
                    _ya_registrado(TIPO_AVISO_SUSALUD),
                    _ya_registrado(TIPO_ESCALADO_SUSALUD),
                )
                .where(
                    LoteFacturacionModelo.enviado_susalud_en.is_(None),
                    LoteFacturacionModelo.estado.not_in(_NO_SUJETOS_A_ENVIO),
                )
                .order_by(LoteFacturacionModelo.id)
            )
        ).all()
        return [
            LotePendienteSusalud(
                lote_id=lote_id,
                periodo=periodo,
                ya_avisado=bool(avisado),
                ya_escalado=bool(escalado),
            )
            for lote_id, periodo, avisado, escalado in filas
        ]

    async def declaraciones(self) -> dict[str, datetime]:
        filas = await self._sesion.execute(
            sa.select(
                DeclaracionSusaludSinFacturacionModelo.periodo,
                DeclaracionSusaludSinFacturacionModelo.registrada_en,
            )
        )
        return {periodo: registrada_en for periodo, registrada_en in filas.all()}

    async def avisos_sin_lotes(self) -> dict[str, frozenset[str]]:
        # Los avisos de un mes sin lotes cuelgan del agregado de sesion.
        filas = await self._sesion.execute(
            sa.select(EventoModelo.tipo_evento, EventoModelo.datos).where(
                EventoModelo.tipo_agregado == "SESION_USUARIO",
                EventoModelo.tipo_evento.in_((TIPO_AVISO_SUSALUD, TIPO_ESCALADO_SUSALUD)),
            )
        )
        avisos: dict[str, set[str]] = {}
        for tipo, datos in filas.all():
            avisos.setdefault(str((datos or {}).get("periodo")), set()).add(tipo)
        return {periodo: frozenset(tipos) for periodo, tipos in avisos.items()}

    async def registrar_declaracion(self, periodo: str, registrada_por: str) -> datetime:
        registrada_en = datetime.now(UTC)
        self._sesion.add(
            DeclaracionSusaludSinFacturacionModelo(
                periodo=periodo, registrada_en=registrada_en, registrada_por=registrada_por
            )
        )
        await self._sesion.flush()
        return registrada_en
