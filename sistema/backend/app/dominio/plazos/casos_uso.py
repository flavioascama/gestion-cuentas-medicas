"""Caso de uso del control de plazos y escalamiento (CU-11, Seccion
5.2.4.3, Tabla 61): "funcion del motor que opera sin intervencion de
ningun actor... se activa con el registro de un hito y evalua
periodicamente su vencimiento". El actor principal es el "temporizador
del sistema" (Tabla 51/Anexo C), no una persona -- por eso sus eventos
no llevan `usuario_origen` (RF-22 atribuye a un usuario interno las
operaciones que ejecuta el ROBOT de automatizacion sobre una sesion que
alguien pidio; esto no es eso, es una corrida periodica sin solicitante).

Ninguno de los cinco hitos mueve `cuenta_medica.estado`: la Tabla 61 solo
describe avisos y escalamientos (y, para el hito 3, una "senal" de
excedida que es informativa, no un estado nuevo del conjunto cerrado de
la Tabla 58) -- por eso este caso de uso no pasa por
`validar_transicion` y sus eventos llevan estado_previo=estado_nuevo=None,
igual que `OBSERVACION_REASIGNADA` en el modulo de observaciones."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.compartido.fecha_peru import fecha_peru
from app.dominio.plazos.puertos import RepositorioPlazos
from app.dominio.plazos.valores import (
    CuentaConPlazo,
    CuentaConVigenciaCartaGarantia,
    ObservacionConPlazo,
    ResumenHito,
    ResumenRevisionPlazos,
)
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj

_ACTOR_TEMPORIZADOR = "temporizador_sistema"


class RevisarVencimientos:
    def __init__(
        self,
        repositorio: RepositorioPlazos,
        observabilidad: Observabilidad,
        reloj: Reloj,
        dias_aviso_previo_vencimiento: int,
        dias_aviso_vigencia_carta_garantia: int,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._dias_aviso_previo_vencimiento = dias_aviso_previo_vencimiento
        self._dias_aviso_vigencia_carta_garantia = dias_aviso_vigencia_carta_garantia

    async def ejecutar(self) -> ResumenRevisionPlazos:
        ahora = self._reloj.ahora()
        return ResumenRevisionPlazos(
            observaciones=await self._revisar_observaciones(ahora),
            lotes_rechazados=await self._revisar_cuentas(
                await self._repositorio.cuentas_rechazadas(),
                ahora,
                tipo_evento_aviso="LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER",
                tipo_evento_escalado="LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO",
            ),
            auditorias=await self._revisar_cuentas(
                await self._repositorio.cuentas_en_auditoria(),
                ahora,
                tipo_evento_aviso="AUDITORIA_PLAZO_PROXIMO_A_VENCER",
                tipo_evento_escalado="AUDITORIA_EXCEDIDA",
            ),
            liquidaciones=await self._revisar_cuentas(
                await self._repositorio.cuentas_liquidadas(),
                ahora,
                tipo_evento_aviso="LIQUIDACION_PAGO_PROXIMO_A_VENCER",
                tipo_evento_escalado="LIQUIDACION_PAGO_VENCIDO_ESCALADO",
            ),
            cartas_garantia=await self._revisar_cartas_garantia(ahora),
        )

    async def _revisar_observaciones(self, ahora: datetime) -> ResumenHito:
        hitos = await self._repositorio.observaciones_abiertas()
        avisados = escalados = 0
        for hito in hitos:
            vencimiento = hito.abierta_desde + timedelta(days=hito.plazo_dias)
            if ahora >= vencimiento and not hito.ya_escalada:
                await self._registrar_observacion(hito, "OBSERVACION_PLAZO_VENCIDO_ESCALADO")
                escalados += 1
            elif self._proximo_a_vencer(ahora, vencimiento) and not hito.ya_avisada:
                await self._registrar_observacion(hito, "OBSERVACION_PLAZO_PROXIMO_A_VENCER")
                avisados += 1
        return ResumenHito(revisados=len(hitos), avisados=avisados, escalados=escalados)

    async def _registrar_observacion(self, hito: ObservacionConPlazo, tipo_evento: str) -> None:
        await self._registrar(
            cuenta_medica_id=hito.cuenta_medica_id,
            tipo_evento=tipo_evento,
            datos={"observacion_id": hito.observacion_id, "plazo_dias": hito.plazo_dias},
        )

    async def _revisar_cuentas(
        self,
        hitos: list[CuentaConPlazo],
        ahora: datetime,
        *,
        tipo_evento_aviso: str,
        tipo_evento_escalado: str,
    ) -> ResumenHito:
        avisados = escalados = 0
        for hito in hitos:
            vencimiento = hito.hito_desde + timedelta(days=hito.plazo_dias)
            if ahora >= vencimiento and not hito.ya_escalada:
                await self._registrar(
                    cuenta_medica_id=hito.cuenta_medica_id,
                    tipo_evento=tipo_evento_escalado,
                    datos={"plazo_dias": hito.plazo_dias},
                )
                escalados += 1
            elif self._proximo_a_vencer(ahora, vencimiento) and not hito.ya_avisada:
                await self._registrar(
                    cuenta_medica_id=hito.cuenta_medica_id,
                    tipo_evento=tipo_evento_aviso,
                    datos={"plazo_dias": hito.plazo_dias},
                )
                avisados += 1
        return ResumenHito(revisados=len(hitos), avisados=avisados, escalados=escalados)

    async def _revisar_cartas_garantia(self, ahora: datetime) -> ResumenHito:
        hitos = await self._repositorio.cuentas_con_carta_garantia_por_vencer()
        avisados = 0
        for hito in hitos:
            if (
                self._carta_garantia_proxima_a_vencer(fecha_peru(ahora), hito)
                and not hito.ya_avisada
            ):
                await self._registrar(
                    cuenta_medica_id=hito.cuenta_medica_id,
                    tipo_evento="CARTA_GARANTIA_PROXIMA_A_VENCER",
                    datos={"vigente_hasta": hito.vigente_hasta.isoformat()},
                )
                avisados += 1
        return ResumenHito(revisados=len(hitos), avisados=avisados)

    def _carta_garantia_proxima_a_vencer(
        self, hoy: date, hito: CuentaConVigenciaCartaGarantia
    ) -> bool:
        dias_restantes = (hito.vigente_hasta - hoy).days
        return 0 <= dias_restantes <= self._dias_aviso_vigencia_carta_garantia

    def _proximo_a_vencer(self, ahora: datetime, vencimiento: datetime) -> bool:
        dias_restantes = (vencimiento - ahora).days
        return 0 <= dias_restantes <= self._dias_aviso_previo_vencimiento

    async def _registrar(
        self, *, cuenta_medica_id: int, tipo_evento: str, datos: dict[str, Any]
    ) -> None:
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=tipo_evento,
                actor=_ACTOR_TEMPORIZADOR,
                estado_previo=None,
                estado_nuevo=None,
                datos=datos,
            )
        )
