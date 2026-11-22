"""Adaptador del puerto GestorSesion (Seccion 5.2, AD-06): credencial firmada
de sesion mediante JWT (HS256), con la clave y la duracion de Configuracion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import SesionExpiradaError, SesionInvalidaError
from app.dominio.acceso.puertos import CargaSesion, GestorSesion
from app.dominio.puertos_comunes import Reloj

_ALGORITMO = "HS256"


class GestorSesionJwt(GestorSesion):
    def __init__(self, clave_firma: str, duracion_minutos: int, reloj: Reloj) -> None:
        self._clave_firma = clave_firma
        self._duracion_minutos = duracion_minutos
        self._reloj = reloj

    def emitir(self, usuario: Usuario) -> str:
        assert usuario.id is not None, "No se puede emitir sesion para un usuario sin persistir"
        ahora = self._reloj.ahora()
        carga: dict[str, object] = {
            "sub": str(usuario.id),
            "nombre_usuario": usuario.nombre_usuario,
            # Solo para que la pantalla muestre a la persona: el servidor no lo lee.
            "nombres": usuario.nombres,
            "roles": [rol.value for rol in usuario.roles],
            # Control C-01 (Seccion 5.2.7): identificador de ESTA
            # credencial, no del usuario -- es lo que CerrarSesion revoca
            # sin invalidar las demas sesiones que el usuario pueda tener
            # abiertas en otro dispositivo.
            "jti": str(uuid4()),
            "iat": ahora,
            "exp": ahora + timedelta(minutes=self._duracion_minutos),
        }
        # Solo va cuando hace falta: la pantalla lleva a cambiar la clave. El
        # servidor no confia en este dato, lee el del usuario en cada pedido.
        if usuario.debe_cambiar_clave:
            carga["cambiar_clave"] = True
        return jwt.encode(carga, self._clave_firma, algorithm=_ALGORITMO)

    def verificar(self, token: str) -> CargaSesion:
        try:
            carga = jwt.decode(token, self._clave_firma, algorithms=[_ALGORITMO])
        except jwt.ExpiredSignatureError as error:
            raise SesionExpiradaError("La sesión venció, vuelva a iniciar sesión.") from error
        except jwt.InvalidTokenError as error:
            raise SesionInvalidaError("La credencial de sesión no es válida.") from error

        try:
            roles = frozenset(NombreRol(rol) for rol in carga["roles"])
            return CargaSesion(
                usuario_id=int(carga["sub"]),
                nombre_usuario=carga["nombre_usuario"],
                roles=roles,
                jti=carga["jti"],
                expira_en=datetime.fromtimestamp(carga["exp"], tz=UTC),
                debe_cambiar_clave=carga.get("cambiar_clave") is True,
                emitida_en=datetime.fromtimestamp(carga["iat"], tz=UTC) if "iat" in carga else None,
            )
        except (KeyError, ValueError) as error:
            raise SesionInvalidaError("La credencial de sesión no es válida.") from error
