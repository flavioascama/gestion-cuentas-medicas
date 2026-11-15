"""Puerto del control de plazos y escalamiento (Seccion 5.2.4.3, Tabla
61). Un metodo por hito: cada uno ya resuelve, del lado del adaptador,
el plazo que corresponde (columna de `iafas` o parametro del sistema) y
si ya existe un aviso o un escalamiento para la ocurrencia VIGENTE del
hito (no una de un ciclo anterior del mismo agregado)."""

from __future__ import annotations

from typing import Protocol

from app.dominio.plazos.valores import (
    CuentaConPlazo,
    CuentaConVigenciaCartaGarantia,
    ObservacionConPlazo,
)


class RepositorioPlazos(Protocol):
    async def observaciones_abiertas(self) -> list[ObservacionConPlazo]:
        """Hito 1: observaciones en estado ABIERTA."""
        ...

    async def cuentas_rechazadas(self) -> list[CuentaConPlazo]:
        """Hito 2: cuentas en RECHAZADA, pendientes de reenvio."""
        ...

    async def cuentas_en_auditoria(self) -> list[CuentaConPlazo]:
        """Hito 3: cuentas en EN_AUDITORIA, a la espera del resultado."""
        ...

    async def cuentas_liquidadas(self) -> list[CuentaConPlazo]:
        """Hito 4: cuentas en LIQUIDADA o LIQUIDADA_PARCIAL, a la
        espera del pago."""
        ...

    async def cuentas_con_carta_garantia_por_vencer(
        self,
    ) -> list[CuentaConVigenciaCartaGarantia]:
        """Hito 5: cuentas aun no remitidas (REGISTRADA o FACTURADA) con
        una vigencia de carta de garantia registrada en su
        acreditacion."""
        ...
