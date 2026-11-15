"""Puerto del contexto de cierre y anulacion de la cuenta medica
(Seccion 5.2.4.1; CU-13, RF-21)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.dominio.cierre.valores import DatosNuevaSolicitudAnulacion, SolicitudAnulacion


class RepositorioSolicitudesAnulacion(Protocol):
    async def crear(self, datos: DatosNuevaSolicitudAnulacion) -> int:
        """Devuelve el id de la solicitud creada, en estado PENDIENTE."""
        ...

    async def obtener(self, solicitud_id: int) -> SolicitudAnulacion | None: ...

    async def obtener_pendiente_por_cuenta(
        self, cuenta_medica_id: int
    ) -> SolicitudAnulacion | None:
        """None si la cuenta no tiene ninguna solicitud PENDIENTE."""
        ...

    async def listar_pendientes(self) -> list[SolicitudAnulacion]:
        """La bandeja del jefe de cuentas medicas: todas las
        solicitudes PENDIENTE, de cualquier cuenta."""
        ...

    async def resolver(
        self, solicitud_id: int, aprobada: bool, resuelto_por: str, resuelto_en: datetime
    ) -> None:
        """Deja la solicitud en APROBADA o RECHAZADA."""
        ...
