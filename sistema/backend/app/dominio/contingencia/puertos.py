"""Puertos del modo de contingencia."""

from __future__ import annotations

from typing import Protocol

from app.dominio.contingencia.valores import (
    IdentidadLoteS01,
    RegistroContingencia,
    ResumenTrabajo,
)


class RepositorioContingencia(Protocol):
    async def ultimo_trabajo(
        self, tipo_trabajo: str, clave: str, valor: int
    ) -> ResumenTrabajo | None:
        """La solicitud mas reciente de ese tipo para esa cuenta o lote
        (`carga_util[clave] == valor`), o None si nunca se pidio."""
        ...

    async def obtener_estado_lote(self, lote_id: int) -> str | None: ...

    async def marcar_lote_observado(self, lote_id: int) -> None: ...

    async def identidad_lote_s01(self, lote_id: int) -> IdentidadLoteS01 | None:
        """None si el lote no existe."""
        ...

    async def cobertura_vigente_no_conforme(self, cuenta_medica_id: int) -> bool:
        """Si la acreditacion vigente es la registrada en contingencia y el
        jefe la reviso no conforme (control C-18)."""
        ...

    async def listar_registros(self) -> list[RegistroContingencia]:
        """Todos los registros en contingencia con su revision, los mas
        recientes primero."""
        ...
