"""Vencimiento vigente de cada cuenta (RNF-06: "el estado vigente y el
plazo de cada cuenta visibles en la bandeja y en el detalle"). Reusa los
mismos hitos que el control de plazos (Tabla 61): el plazo que se ve en la
pantalla es el mismo que dispara los avisos y escalamientos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum

from app.dominio.plazos.puertos import RepositorioPlazos
from app.dominio.puertos_comunes import Reloj


class HitoPlazo(StrEnum):
    OBSERVACION = "OBSERVACION"  # respuesta a una observacion de la IAFAS
    REENVIO = "REENVIO"  # correccion y reenvio de una cuenta rechazada
    AUDITORIA = "AUDITORIA"  # comunicacion del resultado de la auditoria
    PAGO = "PAGO"  # pago de la liquidacion
    COBERTURA = "COBERTURA"  # vigencia de la cobertura antes de remitir


@dataclass(frozen=True, slots=True)
class Vencimiento:
    cuenta_medica_id: int
    hito: HitoPlazo
    vence_en: datetime
    vencido: bool
    por_vencer: bool


def _utc(instante: datetime) -> datetime:
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


class ConsultarVencimientos:
    """El vencimiento mas proximo de cada cuenta con un plazo en curso."""

    def __init__(
        self, repositorio: RepositorioPlazos, reloj: Reloj, dias_aviso_previo: int
    ) -> None:
        self._repositorio = repositorio
        self._reloj = reloj
        self._dias_aviso_previo = dias_aviso_previo

    async def ejecutar(self) -> list[Vencimiento]:
        candidatos: list[tuple[int, HitoPlazo, datetime]] = [
            (
                o.cuenta_medica_id,
                HitoPlazo.OBSERVACION,
                _utc(o.abierta_desde) + timedelta(days=o.plazo_dias),
            )
            for o in await self._repositorio.observaciones_abiertas()
        ]
        for hito, cuentas in (
            (HitoPlazo.REENVIO, await self._repositorio.cuentas_rechazadas()),
            (HitoPlazo.AUDITORIA, await self._repositorio.cuentas_en_auditoria()),
            (HitoPlazo.PAGO, await self._repositorio.cuentas_liquidadas()),
        ):
            candidatos.extend(
                (c.cuenta_medica_id, hito, _utc(c.hito_desde) + timedelta(days=c.plazo_dias))
                for c in cuentas
            )
        candidatos.extend(
            (
                c.cuenta_medica_id,
                HitoPlazo.COBERTURA,
                datetime.combine(c.vigente_hasta, time.max, UTC),
            )
            for c in await self._repositorio.cuentas_con_carta_garantia_por_vencer()
        )
        return self._mas_proximo_por_cuenta(candidatos)

    def _mas_proximo_por_cuenta(
        self, candidatos: list[tuple[int, HitoPlazo, datetime]]
    ) -> list[Vencimiento]:
        ahora = _utc(self._reloj.ahora())
        aviso = timedelta(days=self._dias_aviso_previo)
        proximos: dict[int, tuple[HitoPlazo, datetime]] = {}
        for cuenta_id, hito, vence_en in candidatos:
            if cuenta_id not in proximos or vence_en < proximos[cuenta_id][1]:
                proximos[cuenta_id] = (hito, vence_en)
        return [
            Vencimiento(
                cuenta_medica_id=cuenta_id,
                hito=hito,
                vence_en=vence_en,
                vencido=vence_en < ahora,
                por_vencer=ahora <= vence_en <= ahora + aviso,
            )
            for cuenta_id, (hito, vence_en) in sorted(proximos.items())
        ]
