"""Puerto del modulo de trazabilidad con panel de control gerencial
(Seccion 6.2; CU-14 a CU-16)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.dominio.trazabilidad.valores import (
    DocumentoExpediente,
    FiltroIndicadores,
    HistorialCuenta,
    HistorialLote,
    IndicadoresCiclo,
)


class RepositorioTrazabilidad(Protocol):
    async def existe_cuenta(self, cuenta_medica_id: int) -> bool: ...

    async def historial_de_cuenta(self, cuenta_medica_id: int) -> HistorialCuenta:
        """Reconstruye el historial completo de la cuenta a partir de
        sus eventos y verifica la integridad de esa cadena (RT-01,
        RT-13, control C-10)."""
        ...

    async def documentos_de_cuenta(self, cuenta_medica_id: int) -> list[DocumentoExpediente]:
        """CU-16: los documentos asociados que acompanan al historial
        en el expediente de auditoria."""
        ...

    async def existe_lote(self, lote_id: int) -> bool: ...

    async def historial_de_lote(self, lote_id: int) -> HistorialLote:
        """RT-13: los eventos del lote en orden, con la verificacion de
        su cadena."""
        ...

    async def calcular_indicadores(
        self, filtro: FiltroIndicadores, ahora: datetime | None = None
    ) -> IndicadoresCiclo:
        """CU-15: las proyecciones del panel de control gerencial,
        calculadas a partir de los eventos y de las entidades del
        ciclo -- nunca de un registro manual (R3.4). `ahora` es el
        instante contra el que se mide el tiempo de las cuentas abiertas
        (el reloj del caso de uso; None usa el reloj del sistema)."""
        ...
