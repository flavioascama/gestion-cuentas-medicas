"""Puerto de lectura de avisos: los eventos del almacen cuyo tipo es un
aviso, con la cuenta o el lote al que pertenecen."""

from __future__ import annotations

from typing import Protocol

from app.dominio.avisos.valores import EventoAviso


class RepositorioAvisos(Protocol):
    async def listar(self, tipos_evento: list[str], limite: int) -> list[EventoAviso]:
        """Los mas recientes primero."""
        ...

    async def evaluar_atencion(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        """Los mismos avisos, en el mismo orden, con `atendido` resuelto
        contra lo que paso despues en el almacen y en la cola."""
        ...
