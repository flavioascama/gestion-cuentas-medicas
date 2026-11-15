"""Adaptador del puerto VerificadorClave (Seccion 5.2), con bcrypt directo.

Se usa el paquete `bcrypt` en vez de `passlib[bcrypt]`: passlib esta sin
mantenimiento y su rutina interna de autodeteccion de version falla con las
versiones recientes de `bcrypt` (`AttributeError: module 'bcrypt' has no
attribute '__about__'`, seguido de un `ValueError` espurio sobre longitud de
clave). Ver docs/DECISIONES.md.
"""

from __future__ import annotations

import bcrypt

from app.dominio.acceso.puertos import VerificadorClave


class VerificadorClaveBcrypt(VerificadorClave):
    def generar_hash(self, clave: str) -> str:
        return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    def verificar(self, clave: str, hash_clave: str) -> bool:
        return bcrypt.checkpw(clave.encode("utf-8"), hash_clave.encode("ascii"))
