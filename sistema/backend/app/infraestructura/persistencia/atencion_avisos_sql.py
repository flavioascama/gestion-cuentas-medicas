"""Decide si cada aviso ya fue atendido, a partir de lo que paso despues en
el almacen de eventos y en la cola de trabajos (rediseno de la bandeja de
avisos, 2026-11-12: la bandeja mostraba igual un aviso de una cuenta que ya
se habia corregido que uno pendiente).

Reglas, en orden:
- Ruptura de la cadena, acceso no permitido y resultado de una anulacion:
  nunca se dan por atendidos solos; quien los recibe los marca.
- Registro en contingencia: atendido cuando el jefe lo reviso (C-18).
- Falla del proceso de automatizacion: atendida cuando un trabajo posterior
  del mismo tipo y destino se completo, o cuando la operacion ya no hace
  falta (la cuenta ya tiene acreditacion, el lote ya paso del validador).
- Lote rechazado: atendido cuando ninguna de sus cuentas sigue RECHAZADA.
- Envio a SUSALUD por vencer o vencido: atendido cuando el lote ya tiene
  fecha de envio a SUSALUD.
- Resultado de auditoria por vencer o vencido: atendido tambien cuando se
  registro la conformidad de la auditoria despues del aviso (CU-07).
- Avisos de plazo de una cuenta o de un lote: atendidos cuando ese
  agregado cambio de estado despues del aviso (la observacion se
  respondio, la cuenta se corrigio, el pago se registro...)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.avisos.valores import (
    TIPO_AVISO_TRABAJO_AGOTADO,
    TIPO_EVENTO_AVISO_ATENDIDO,
    TIPOS_AVISO_MARCABLES,
    EventoAviso,
)
from app.dominio.observaciones.conformidad import TIPO_EVENTO_CONFORMIDAD
from app.infraestructura.persistencia.modelos_declaracion_susalud import (
    DeclaracionSusaludSinFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    EventoModelo,
    LoteFacturacionModelo,
    TrabajoModelo,
)

_CONTINGENCIAS = frozenset(
    {"CONTINGENCIA_COBERTURA_REGISTRADA", "CONTINGENCIA_VALIDACION_REGISTRADA"}
)
_ESTADOS_LOTE_ESPERANDO_VALIDADOR = frozenset({"GENERADO", "CARGADO_VALIDADOR"})
_ENVIO_SUSALUD = frozenset({"SUSALUD_ENVIO_PROXIMO_A_VENCER", "SUSALUD_ENVIO_VENCIDO_ESCALADO"})
_PLAZO_AUDITORIA = frozenset({"AUDITORIA_PLAZO_PROXIMO_A_VENCER", "AUDITORIA_EXCEDIDA"})


def _utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


def _destino_trabajo(carga: dict[str, Any]) -> tuple[str, object] | None:
    for clave in ("cuenta_medica_id", "lote_id", "plataforma"):
        if carga.get(clave) is not None:
            return (clave, carga[clave])
    return None


@dataclass(frozen=True, slots=True)
class _Contexto:
    cambios: dict[tuple[str, int], datetime]
    revisados: set[str]
    completados: dict[tuple[str, tuple[str, object]], datetime]
    acreditadas: set[int]
    estado_cuenta: dict[int, str]
    estado_lote: dict[int, str]
    enviados_susalud: set[int]
    conformidades: dict[int, datetime]
    declarados: set[str]
    marcados: set[str]


class EvaluadorAtencionAvisos:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def evaluar(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        if not avisos:
            return []
        cuentas = {a.cuenta_medica_id for a in avisos if a.cuenta_medica_id is not None}
        for aviso in avisos:
            cuentas.update(int(c) for c in aviso.datos.get("cuentas_afectadas") or [])
        lotes = {a.lote_id for a in avisos if a.lote_id is not None}
        contexto = _Contexto(
            cambios=await self._ultimo_cambio_de_estado(cuentas, lotes),
            revisados=await self._contingencias_revisadas(),
            completados=await self._trabajos_completados(),
            acreditadas=await self._cuentas_acreditadas(cuentas),
            estado_cuenta=await self._estados(CuentaMedicaModelo, cuentas),
            estado_lote=await self._estados(LoteFacturacionModelo, lotes),
            enviados_susalud=await self._enviados_susalud(lotes),
            conformidades=await self._conformidades(cuentas),
            declarados=await self._declarados(),
            marcados=await self._marcados(),
        )
        return [replace(aviso, atendido=_atendido(aviso, contexto)) for aviso in avisos]

    async def _ultimo_cambio_de_estado(
        self, cuentas: set[int], lotes: set[int]
    ) -> dict[tuple[str, int], datetime]:
        filas = (
            await self._sesion.execute(
                sa.select(
                    EventoModelo.tipo_agregado,
                    EventoModelo.agregado_id,
                    sa.func.max(EventoModelo.ocurrido_en),
                )
                .where(
                    EventoModelo.estado_nuevo.is_not(None),
                    sa.or_(
                        sa.and_(
                            EventoModelo.tipo_agregado == "CUENTA",
                            EventoModelo.agregado_id.in_(cuentas),
                        ),
                        sa.and_(
                            EventoModelo.tipo_agregado == "LOTE",
                            EventoModelo.agregado_id.in_(lotes),
                        ),
                    ),
                )
                .group_by(EventoModelo.tipo_agregado, EventoModelo.agregado_id)
            )
        ).all()
        return {(tipo, agregado): _utc(instante) for tipo, agregado, instante in filas}

    async def _marcados(self) -> set[str]:
        filas = await self._sesion.execute(
            sa.select(EventoModelo.datos).where(
                EventoModelo.tipo_evento == TIPO_EVENTO_AVISO_ATENDIDO
            )
        )
        return {str((datos or {}).get("aviso_evento_id")) for (datos,) in filas.all()}

    async def _contingencias_revisadas(self) -> set[str]:
        filas = await self._sesion.execute(
            sa.select(EventoModelo.datos).where(EventoModelo.tipo_evento == "CONTINGENCIA_REVISADA")
        )
        return {str((datos or {}).get("registro_evento_id")) for (datos,) in filas.all()}

    async def _trabajos_completados(self) -> dict[tuple[str, tuple[str, object]], datetime]:
        filas = await self._sesion.execute(
            sa.select(
                TrabajoModelo.tipo, TrabajoModelo.carga_util, TrabajoModelo.actualizado_en
            ).where(TrabajoModelo.estado == "COMPLETADO")
        )
        completados: dict[tuple[str, tuple[str, object]], datetime] = {}
        for tipo, carga, instante in filas.all():
            destino = _destino_trabajo(carga or {})
            if destino is None:
                continue
            clave = (tipo, destino)
            if clave not in completados or _utc(instante) > completados[clave]:
                completados[clave] = _utc(instante)
        return completados

    async def _cuentas_acreditadas(self, cuentas: set[int]) -> set[int]:
        if not cuentas:
            return set()
        filas = await self._sesion.execute(
            sa.select(AcreditacionModelo.cuenta_id).where(AcreditacionModelo.cuenta_id.in_(cuentas))
        )
        return {cuenta for (cuenta,) in filas.all()}

    async def _conformidades(self, cuentas: set[int]) -> dict[int, datetime]:
        if not cuentas:
            return {}
        filas = await self._sesion.execute(
            sa.select(EventoModelo.cuenta_medica_id, sa.func.max(EventoModelo.ocurrido_en))
            .where(
                EventoModelo.tipo_evento == TIPO_EVENTO_CONFORMIDAD,
                EventoModelo.cuenta_medica_id.in_(cuentas),
            )
            .group_by(EventoModelo.cuenta_medica_id)
        )
        return {int(cuenta): _utc(instante) for cuenta, instante in filas.all()}

    async def _declarados(self) -> set[str]:
        filas = await self._sesion.execute(
            sa.select(DeclaracionSusaludSinFacturacionModelo.periodo)
        )
        return {periodo for (periodo,) in filas.all()}

    async def _enviados_susalud(self, lotes: set[int]) -> set[int]:
        if not lotes:
            return set()
        filas = await self._sesion.execute(
            sa.select(LoteFacturacionModelo.id).where(
                LoteFacturacionModelo.id.in_(lotes),
                LoteFacturacionModelo.enviado_susalud_en.is_not(None),
            )
        )
        return {lote for (lote,) in filas.all()}

    async def _estados(self, modelo: Any, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        filas = await self._sesion.execute(
            sa.select(modelo.id, modelo.estado).where(modelo.id.in_(ids))
        )
        return {identificador: estado for identificador, estado in filas.all()}


def _atendido(aviso: EventoAviso, contexto: _Contexto) -> bool:
    if aviso.tipo_evento in TIPOS_AVISO_MARCABLES:
        return aviso.evento_id in contexto.marcados
    # Solo se listan los correos que siguen por revisar: al vincularlos o
    # descartarlos dejan de ser un aviso.
    if aviso.tipo_evento == "CORREO_IAFAS_POR_REVISAR":
        return False
    if aviso.tipo_evento in _CONTINGENCIAS:
        return aviso.evento_id in contexto.revisados
    if aviso.tipo_evento == TIPO_AVISO_TRABAJO_AGOTADO:
        return _trabajo_atendido(aviso, contexto)
    if aviso.tipo_evento in _ENVIO_SUSALUD:
        if aviso.lote_id is None:
            return str(aviso.datos.get("periodo")) in contexto.declarados
        return aviso.lote_id in contexto.enviados_susalud
    conformidad = contexto.conformidades.get(aviso.cuenta_medica_id or 0)
    if (
        aviso.tipo_evento in _PLAZO_AUDITORIA
        and conformidad is not None
        and conformidad > _utc(aviso.ocurrido_en)
    ):
        return True
    if aviso.tipo_evento == "LOTE_RECHAZADO":
        afectadas = [int(c) for c in aviso.datos.get("cuentas_afectadas") or []]
        return bool(afectadas) and all(
            contexto.estado_cuenta.get(c) != "RECHAZADA" for c in afectadas
        )
    agregado = (
        ("CUENTA", aviso.cuenta_medica_id)
        if aviso.cuenta_medica_id is not None
        else ("LOTE", aviso.lote_id)
    )
    cambio = contexto.cambios.get(agregado)  # type: ignore[arg-type]
    return cambio is not None and cambio > _utc(aviso.ocurrido_en)


def _trabajo_atendido(aviso: EventoAviso, contexto: _Contexto) -> bool:
    tipo = str(aviso.datos.get("tipo_trabajo"))
    if tipo == "CONSULTAR_COBERTURA" and aviso.cuenta_medica_id in contexto.acreditadas:
        return True
    if (
        tipo == "CARGAR_LOTE_VALIDADOR"
        and aviso.lote_id is not None
        and contexto.estado_lote.get(aviso.lote_id) not in _ESTADOS_LOTE_ESPERANDO_VALIDADOR
    ):
        return True
    destino = _destino_trabajo(
        {
            "cuenta_medica_id": aviso.cuenta_medica_id,
            "lote_id": aviso.lote_id,
            "plataforma": aviso.datos.get("plataforma"),
        }
    )
    completado = contexto.completados.get((tipo, destino)) if destino else None
    return completado is not None and completado > _utc(aviso.ocurrido_en)
