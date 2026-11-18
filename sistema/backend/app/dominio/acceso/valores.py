"""Reglas de dominio del contexto de acceso que no requieren su propio
Protocol (Seccion 2.2 de GUIA_ESTILO_CODIGO.md: patron Objeto de valor,
pero sin envolver la clave en texto plano en un tipo propio -- se valida
y se descarta de inmediato, nunca se conserva)."""

from __future__ import annotations

from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.errores import ClaveDebilError

# Control C-01 (Seccion 5.2.7 de la tesis, RNF-09): "las contrasenas tienen
# una longitud minima de doce caracteres con mayusculas, minusculas y
# digitos".
_LARGO_MINIMO_CLAVE = 12


def validar_politica_clave(clave: str) -> None:
    """Lanza ClaveDebilError si `clave` no cumple el control C-01. La usan
    RegistrarUsuario (CU-18) y CambiarClavePropia (cambio_clave.py)."""

    cumple = (
        len(clave) >= _LARGO_MINIMO_CLAVE
        and any(caracter.isupper() for caracter in clave)
        and any(caracter.islower() for caracter in clave)
        and any(caracter.isdigit() for caracter in clave)
    )
    if not cumple:
        raise ClaveDebilError()


# Ley N. 26842, art. 25: la informacion del acto medico es reservada.
# El diagnostico, la historia clinica, los procedimientos y los
# productos dispensados solo los ven los roles que trabajan sobre la
# atencion (registro, codificacion, observaciones y supervision).
# Tesoreria consulta la cuenta para liquidar y conciliar el pago, y no
# los necesita (minimo privilegio, control C-02).
ROLES_CON_DATOS_CLINICOS = frozenset({NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE})


def accede_a_datos_clinicos(roles: frozenset[NombreRol]) -> bool:
    return bool(roles & ROLES_CON_DATOS_CLINICOS)
