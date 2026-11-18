"""Adaptador del puerto RepositorioUsuarios (Seccion 5.2, patron Repositorio)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import NombreUsuarioDuplicadoError, RolDesconocidoError
from app.dominio.acceso.puertos import RepositorioUsuarios
from app.infraestructura.persistencia.modelos_acceso import RolModelo, UsuarioModelo


def _a_entidad(modelo: UsuarioModelo) -> Usuario:
    return Usuario(
        id=modelo.id,
        nombre_usuario=modelo.nombre_usuario,
        nombres=modelo.nombres,
        hash_clave=modelo.hash_clave,
        activo=modelo.activo,
        roles=frozenset(NombreRol(r.nombre) for r in modelo.roles),
        intentos_fallidos=modelo.intentos_fallidos,
        bloqueado_hasta=modelo.bloqueado_hasta,
        debe_cambiar_clave=modelo.debe_cambiar_clave,
    )


class RepositorioUsuariosSql(RepositorioUsuarios):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_por_nombre_usuario(self, nombre_usuario: str) -> Usuario | None:
        resultado = await self._sesion.execute(
            sa.select(UsuarioModelo).where(UsuarioModelo.nombre_usuario == nombre_usuario)
        )
        modelo = resultado.scalar_one_or_none()
        return _a_entidad(modelo) if modelo else None

    async def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        modelo = await self._sesion.get(UsuarioModelo, usuario_id)
        return _a_entidad(modelo) if modelo else None

    async def listar(self) -> list[Usuario]:
        resultado = await self._sesion.execute(
            sa.select(UsuarioModelo).order_by(UsuarioModelo.nombre_usuario)
        )
        return [_a_entidad(modelo) for modelo in resultado.scalars().all()]

    async def crear(self, usuario: Usuario) -> Usuario:
        nombres_rol = [rol.value for rol in usuario.roles]
        resultado_roles = await self._sesion.execute(
            sa.select(RolModelo).where(RolModelo.nombre.in_(nombres_rol))
        )
        roles_modelo = list(resultado_roles.scalars().all())
        if len(roles_modelo) != len(usuario.roles):
            encontrados = {modelo.nombre for modelo in roles_modelo}
            faltante = next(nombre for nombre in nombres_rol if nombre not in encontrados)
            raise RolDesconocidoError(faltante)

        modelo = UsuarioModelo(
            nombre_usuario=usuario.nombre_usuario,
            nombres=usuario.nombres,
            hash_clave=usuario.hash_clave,
            activo=usuario.activo,
            debe_cambiar_clave=usuario.debe_cambiar_clave,
            roles=roles_modelo,
        )
        self._sesion.add(modelo)
        try:
            await self._sesion.commit()
        except IntegrityError as error:
            await self._sesion.rollback()
            raise NombreUsuarioDuplicadoError(usuario.nombre_usuario) from error
        await self._sesion.refresh(modelo, attribute_names=["id", "roles"])
        return _a_entidad(modelo)

    async def actualizar(
        self,
        usuario_id: int,
        nombres: str | None = None,
        roles: frozenset[NombreRol] | None = None,
        activo: bool | None = None,
    ) -> Usuario | None:
        modelo = await self._sesion.get(UsuarioModelo, usuario_id)
        if modelo is None:
            return None
        if nombres is not None:
            modelo.nombres = nombres
        if activo is not None:
            modelo.activo = activo
        if roles is not None:
            nombres_rol = [rol.value for rol in roles]
            resultado_roles = await self._sesion.execute(
                sa.select(RolModelo).where(RolModelo.nombre.in_(nombres_rol))
            )
            roles_modelo = list(resultado_roles.scalars().all())
            if len(roles_modelo) != len(roles):
                encontrados = {modelo_rol.nombre for modelo_rol in roles_modelo}
                faltante = next(nombre for nombre in nombres_rol if nombre not in encontrados)
                raise RolDesconocidoError(faltante)
            modelo.roles = roles_modelo
        await self._sesion.commit()
        await self._sesion.refresh(modelo, attribute_names=["roles"])
        return _a_entidad(modelo)

    async def incrementar_intentos_fallidos(self, usuario_id: int) -> int:
        # Sin RETURNING a proposito: esta suite corre lo mismo contra
        # SQLite en memoria (pruebas/) que contra Postgres real
        # (pruebas_integracion/), y RETURNING depende de la version de
        # SQLite empaquetada con cada interprete -- un UPDATE y un SELECT
        # aparte funcionan igual en los dos motores.
        await self._sesion.execute(
            sa.update(UsuarioModelo)
            .where(UsuarioModelo.id == usuario_id)
            .values(intentos_fallidos=UsuarioModelo.intentos_fallidos + 1)
        )
        await self._sesion.commit()
        resultado = await self._sesion.execute(
            sa.select(UsuarioModelo.intentos_fallidos).where(UsuarioModelo.id == usuario_id)
        )
        return resultado.scalar_one()

    async def bloquear(self, usuario_id: int, hasta: datetime) -> None:
        await self._sesion.execute(
            sa.update(UsuarioModelo)
            .where(UsuarioModelo.id == usuario_id)
            .values(bloqueado_hasta=hasta)
        )
        await self._sesion.commit()

    async def cambiar_clave(self, usuario_id: int, hash_clave: str) -> None:
        await self._sesion.execute(
            sa.update(UsuarioModelo)
            .where(UsuarioModelo.id == usuario_id)
            .values(
                hash_clave=hash_clave,
                debe_cambiar_clave=False,
                intentos_fallidos=0,
                bloqueado_hasta=None,
            )
        )
        await self._sesion.commit()

    async def registrar_inicio_exitoso(self, usuario_id: int) -> None:
        await self._sesion.execute(
            sa.update(UsuarioModelo)
            .where(UsuarioModelo.id == usuario_id)
            .values(intentos_fallidos=0, bloqueado_hasta=None)
        )
        await self._sesion.commit()
