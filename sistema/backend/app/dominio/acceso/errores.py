"""Errores de dominio del contexto de acceso. Sin dependencia de FastAPI ni HTTP.

La capa de API (app/api/dependencias.py, app/api/rutas_auth.py, etc.) los
traduce al formato uniforme de error de la Seccion 10.1.
"""

from __future__ import annotations


class ErrorAcceso(Exception):
    """Base de los errores del contexto de acceso."""


class CredencialesInvalidasError(ErrorAcceso):
    """Nombre de usuario inexistente, clave incorrecta o usuario inactivo.

    Deliberadamente no se distingue el motivo exacto en el mensaje: separar
    'usuario inactivo' de 'clave incorrecta' filtra informacion util para un
    intento de acceso indebido.
    """


class SesionInvalidaError(ErrorAcceso):
    """La credencial firmada no es valida: firma incorrecta o formato invalido."""


class SesionExpiradaError(ErrorAcceso):
    """La credencial firmada es valida pero su vigencia ya vencio."""


class NombreUsuarioDuplicadoError(ErrorAcceso):
    def __init__(self, nombre_usuario: str) -> None:
        super().__init__(f"El nombre de usuario '{nombre_usuario}' ya existe.")
        self.nombre_usuario = nombre_usuario


class RolDesconocidoError(ErrorAcceso):
    def __init__(self, rol: str) -> None:
        super().__init__(f"El rol '{rol}' no pertenece al conjunto de roles del sistema.")
        self.rol = rol


class RolesRequeridosError(ErrorAcceso):
    """Un usuario debe tener al menos un rol asignado (RF-19)."""

    def __init__(self) -> None:
        super().__init__("El usuario debe tener al menos un rol asignado.")


class UsuarioNoEncontradoError(ErrorAcceso):
    def __init__(self, usuario_id: int) -> None:
        super().__init__(f"No existe el usuario {usuario_id}.")
        self.usuario_id = usuario_id


class ClaveDebilError(ErrorAcceso):
    """Control C-01 (Seccion 5.2.7): la clave no cumple la politica (doce
    caracteres como minimo, con mayuscula, minuscula y digito)."""

    def __init__(self) -> None:
        super().__init__(
            "La clave debe tener al menos doce caracteres e incluir una mayuscula, "
            "una minuscula y un digito."
        )


class CuentaBloqueadaError(ErrorAcceso):
    """Control C-01: se agotaron los cinco intentos y la cuenta quedo
    bloqueada por quince minutos (Seccion 5.2.7, Tabla 28)."""

    def __init__(self, minutos_restantes: int) -> None:
        super().__init__(
            f"La cuenta esta bloqueada por intentos fallidos; intente de nuevo en "
            f"{minutos_restantes} minuto(s)."
        )
        self.minutos_restantes = minutos_restantes


class SesionRevocadaError(ErrorAcceso):
    """La credencial de sesion es valida y no vencio, pero fue revocada: se
    cerro sesion explicitamente o el usuario fue desactivado despues de
    emitirla (control C-01, "se revoca al cerrar la sesion o al desactivar
    al usuario")."""
