"""Caso de uso de consulta sobre la cola transaccional (Seccion 6.1, 6.2,
Fase 18): `RepositorioTrabajos` es un puerto compartido entre contextos
(`app/dominio/puertos_comunes.py`), sin un modulo de dominio propio hasta
ahora -- este archivo le da uno minimo, nombrado igual que el adaptador
ya existente en `app/infraestructura/cola/`."""

from __future__ import annotations

from app.dominio.puertos_comunes import DetalleTrabajo, RepositorioTrabajos


class ObtenerTrabajo:
    """Seccion 11: `GET /trabajos/{id}`, analista, jefe y tesoreria
    pueden seguir el progreso de un trabajo que encolo cualquier caso de
    uso (verificacion de cobertura, generacion de lote, sesion de
    plataforma, etc.)."""

    def __init__(self, repositorio: RepositorioTrabajos) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, trabajo_id: int) -> DetalleTrabajo | None:
        return await self._repositorio.obtener(trabajo_id)
