"""Esquemas Pydantic de la API de acceso. `hash_clave` nunca se serializa."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.dominio.acceso.entidades import NombreRol, Usuario


class SolicitudInicioSesion(BaseModel):
    nombre_usuario: str
    clave: str


class RespuestaInicioSesion(BaseModel):
    token: str
    tipo: str = "bearer"


class SolicitudCrearUsuario(BaseModel):
    nombre_usuario: str = Field(min_length=3, max_length=50)
    # min_length=12 es solo la cota estructural (falla rapido con un 422
    # claro); la politica completa del control C-01 -- mayuscula,
    # minuscula y digito -- es una regla de negocio y vive en
    # app.dominio.acceso.valores.validar_politica_clave, no aqui
    # ("ninguna regla de negocio en una ruta", GUIA_ESTILO_CODIGO.md,
    # Seccion 2.1).
    clave: str = Field(min_length=12, max_length=200)
    nombres: str = Field(min_length=1, max_length=150)
    roles: list[NombreRol] = Field(min_length=1)


class SolicitudActualizarUsuario(BaseModel):
    """Cada campo en None (el valor por defecto) deja ese dato sin tocar
    -- permite que la pantalla de administracion mande solo lo que el
    administrador cambio realmente (editar nombres, reasignar roles o
    activar/desactivar el acceso, cada una por separado)."""

    nombres: str | None = Field(default=None, min_length=1, max_length=150)
    roles: list[NombreRol] | None = Field(default=None, min_length=1)
    activo: bool | None = None


class RespuestaUsuario(BaseModel):
    id: int
    nombre_usuario: str
    nombres: str
    activo: bool
    roles: list[NombreRol]

    @staticmethod
    def desde_entidad(usuario: Usuario) -> RespuestaUsuario:
        assert usuario.id is not None
        return RespuestaUsuario(
            id=usuario.id,
            nombre_usuario=usuario.nombre_usuario,
            nombres=usuario.nombres,
            activo=usuario.activo,
            roles=sorted(usuario.roles),
        )
