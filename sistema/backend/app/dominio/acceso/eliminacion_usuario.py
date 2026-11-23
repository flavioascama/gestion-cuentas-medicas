"""Eliminar un usuario (2026-11-22): solo el que nunca tuvo actividad en
el sistema, por ejemplo uno creado por error. El que ya ingreso o registro
algo queda en el historial como responsable y solo se puede desactivar."""

from __future__ import annotations

from typing import Protocol

from app.dominio.acceso.casos_uso import _registrar_administracion
from app.dominio.acceso.entidades import Usuario
from app.dominio.acceso.errores import ErrorAcceso, UsuarioNoEncontradoError
from app.dominio.acceso.puertos import RepositorioUsuarios
from app.dominio.puertos_comunes import RegistroEventos


class UsuarioNoEliminableError(ErrorAcceso):
    pass


class EliminacionUsuarios(Protocol):
    async def tiene_actividad(self, usuario: Usuario) -> bool:
        """True si el usuario ya ingreso al sistema o figura en algun
        registro (historial, procedimientos, observaciones)."""
        ...

    async def eliminar(self, usuario_id: int) -> None: ...


class EliminarUsuario:
    def __init__(
        self,
        repositorio: RepositorioUsuarios,
        eliminacion: EliminacionUsuarios,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._repositorio = repositorio
        self._eliminacion = eliminacion
        self._registro_eventos = registro_eventos

    async def ejecutar(self, usuario_id: int, actor_id: int, actor: str) -> None:
        if usuario_id == actor_id:
            raise UsuarioNoEliminableError("No puede eliminar su propio usuario.")
        usuario = await self._repositorio.obtener_por_id(usuario_id)
        if usuario is None:
            raise UsuarioNoEncontradoError(usuario_id)
        if await self._eliminacion.tiene_actividad(usuario):
            raise UsuarioNoEliminableError(
                "El usuario ya tiene actividad en el sistema: solo se puede desactivar."
            )
        await _registrar_administracion(
            self._registro_eventos,
            usuario,
            "USUARIO_ELIMINADO",
            actor,
            {"nombre_usuario": usuario.nombre_usuario},
        )
        await self._eliminacion.eliminar(usuario_id)
