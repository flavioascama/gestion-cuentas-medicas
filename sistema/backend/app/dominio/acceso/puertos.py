"""Puertos del contexto de acceso (Seccion 5.2): interfaces con Protocol,
implementadas en infraestructura. Este modulo no importa SQLAlchemy,
passlib, PyJWT ni FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.acceso.entidades import NombreRol, Usuario


class RepositorioUsuarios(Protocol):
    async def obtener_por_nombre_usuario(self, nombre_usuario: str) -> Usuario | None: ...

    async def obtener_por_id(self, usuario_id: int) -> Usuario | None: ...

    async def listar(self) -> list[Usuario]: ...

    async def crear(self, usuario: Usuario) -> Usuario: ...

    async def actualizar(
        self,
        usuario_id: int,
        nombres: str | None = None,
        roles: frozenset[NombreRol] | None = None,
        activo: bool | None = None,
    ) -> Usuario | None:
        """None si el usuario no existe. Cada parametro en None deja ese
        campo sin tocar. "Eliminar" un usuario es activo=False (nunca se
        borra la fila: RNF-08 exige que el actor de cada evento pasado
        siga siendo identificable)."""
        ...

    async def incrementar_intentos_fallidos(self, usuario_id: int) -> int:
        """Control C-01: suma uno a `intentos_fallidos` y devuelve el
        conteo resultante, para que IniciarSesion decida si ya toca
        bloquear la cuenta."""
        ...

    async def bloquear(self, usuario_id: int, hasta: datetime) -> None:
        """Control C-01: fija `bloqueado_hasta`. No toca `intentos_fallidos`
        (queda como evidencia de cuantos intentos lo motivaron)."""
        ...

    async def registrar_inicio_exitoso(self, usuario_id: int) -> None:
        """Control C-01: un ingreso correcto reinicia el contador de
        intentos fallidos y levanta el bloqueo, si lo hubiera."""
        ...


class VerificadorClave(Protocol):
    """Puerto y adaptador: bcrypt en infraestructura (Seccion 5.2)."""

    def generar_hash(self, clave: str) -> str: ...

    def verificar(self, clave: str, hash_clave: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class CargaSesion:
    """Contenido verificado de una credencial firmada de sesion (AD-06).

    `jti` y `expira_en` sostienen el control C-01: `jti` es el
    identificador unico de ESTA credencial (no del usuario), el que
    CerrarSesion revoca; `expira_en` es hasta cuando tiene sentido
    conservar esa revocacion antes de poder purgarla."""

    usuario_id: int
    nombre_usuario: str
    roles: frozenset[NombreRol]
    jti: str
    expira_en: datetime


class GestorSesion(Protocol):
    """Puerto y adaptador: JWT firmado en infraestructura (Seccion 5.2)."""

    def emitir(self, usuario: Usuario) -> str: ...

    def verificar(self, token: str) -> CargaSesion: ...


class RegistroRevocaciones(Protocol):
    """Puerto del control C-01 ("se revoca al cerrar la sesion o al
    desactivar al usuario"): el JWT deja de ser enteramente sin estado
    (AD-06, Seccion 5.2) para admitir una lista de revocacion explicita,
    consultada en cada solicitud autenticada (`obtener_usuario_actual`)."""

    async def revocar(self, jti: str, expira_en: datetime) -> None: ...

    async def esta_revocado(self, jti: str) -> bool: ...
