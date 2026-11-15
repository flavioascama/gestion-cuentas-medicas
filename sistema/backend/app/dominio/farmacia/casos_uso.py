"""Caso de uso de solo lectura del catalogo GTIN (Fase 19, pantalla de
administracion)."""

from __future__ import annotations

from app.dominio.farmacia.dispensacion import ProductoCatalogo
from app.dominio.farmacia.puertos import (
    CargadorCatalogoGtin,
    RepositorioCatalogoGtin,
    RepositorioProductosCatalogoGtin,
    VersionCatalogoGtin,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos


class ListarVersionesCatalogoGtin:
    def __init__(self, repositorio: RepositorioCatalogoGtin) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[VersionCatalogoGtin]:
        return await self._repositorio.listar_versiones()


class CargarCatalogoGtin:
    """CU-18: el administrador carga una version nueva del catalogo GTIN
    (nunca modifica las anteriores); la carga queda en la bitacora."""

    def __init__(self, cargador: CargadorCatalogoGtin, registro_eventos: RegistroEventos) -> None:
        self._cargador = cargador
        self._registro_eventos = registro_eventos

    async def ejecutar(self, actor: str, usuario_id: int) -> VersionCatalogoGtin:
        version = await self._cargador.cargar()
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento="CATALOGO_GTIN_CARGADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"version_id": version.id, "conteo": version.conteo},
            )
        )
        return version


class ListarProductosCatalogoGtin:
    def __init__(self, repositorio: RepositorioProductosCatalogoGtin) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, version_id: int) -> list[ProductoCatalogo]:
        return await self._repositorio.productos_de_version(version_id)
