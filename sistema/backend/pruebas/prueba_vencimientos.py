"""RNF-06: vencimiento vigente de cada cuenta (el mas proximo de sus
hitos de la Tabla 61), marcado como vencido o por vencer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.dominio.plazos.consulta import ConsultarVencimientos, HitoPlazo
from app.dominio.plazos.valores import (
    CuentaConPlazo,
    CuentaConVigenciaCartaGarantia,
    ObservacionConPlazo,
)

_AHORA = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)


class _Reloj:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _Plazos:
    observaciones: list[ObservacionConPlazo] = field(default_factory=list)
    rechazadas: list[CuentaConPlazo] = field(default_factory=list)
    en_auditoria: list[CuentaConPlazo] = field(default_factory=list)
    liquidadas: list[CuentaConPlazo] = field(default_factory=list)
    cartas: list[CuentaConVigenciaCartaGarantia] = field(default_factory=list)

    async def observaciones_abiertas(self) -> list[ObservacionConPlazo]:
        return self.observaciones

    async def cuentas_rechazadas(self) -> list[CuentaConPlazo]:
        return self.rechazadas

    async def cuentas_en_auditoria(self) -> list[CuentaConPlazo]:
        return self.en_auditoria

    async def cuentas_liquidadas(self) -> list[CuentaConPlazo]:
        return self.liquidadas

    async def cuentas_con_carta_garantia_por_vencer(self) -> list[CuentaConVigenciaCartaGarantia]:
        return self.cartas


def _cuenta(cuenta_id: int, desde: datetime, dias: int) -> CuentaConPlazo:
    return CuentaConPlazo(
        cuenta_medica_id=cuenta_id,
        plazo_dias=dias,
        hito_desde=desde,
        ya_avisada=False,
        ya_escalada=False,
    )


async def prueba_cada_cuenta_muestra_su_vencimiento_mas_proximo() -> None:
    plazos = _Plazos(
        observaciones=[
            ObservacionConPlazo(1, 10, 7, datetime(2026, 11, 10, 12, 0, tzinfo=UTC), False, False)
        ],
        rechazadas=[_cuenta(20, datetime(2026, 11, 1, 12, 0, tzinfo=UTC), 5)],
        en_auditoria=[_cuenta(10, datetime(2026, 11, 1, 12, 0, tzinfo=UTC), 30)],
        cartas=[CuentaConVigenciaCartaGarantia(30, date(2026, 12, 31), False)],
    )
    vencimientos = {
        v.cuenta_medica_id: v
        for v in await ConsultarVencimientos(plazos, _Reloj(), 2).ejecutar()  # type: ignore[arg-type]
    }

    # La 10 tiene dos hitos: cuenta el mas proximo (la observacion, 17/11).
    assert vencimientos[10].hito is HitoPlazo.OBSERVACION
    assert vencimientos[10].vence_en == datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    assert not vencimientos[10].vencido and not vencimientos[10].por_vencer
    # La 20 vencio el 06/11.
    assert vencimientos[20].hito is HitoPlazo.REENVIO and vencimientos[20].vencido
    assert vencimientos[30].hito is HitoPlazo.COBERTURA


async def prueba_un_plazo_dentro_del_aviso_previo_esta_por_vencer() -> None:
    plazos = _Plazos(liquidadas=[_cuenta(5, datetime(2026, 10, 15, 0, 0, tzinfo=UTC), 30)])
    (vencimiento,) = await ConsultarVencimientos(plazos, _Reloj(), 2).ejecutar()  # type: ignore[arg-type]
    assert vencimiento.hito is HitoPlazo.PAGO
    assert vencimiento.por_vencer and not vencimiento.vencido
