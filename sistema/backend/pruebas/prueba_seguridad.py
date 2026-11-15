"""Pruebas unitarias de los adaptadores de seguridad (Seccion 12.1).

El puerto Reloj controla el instante embebido al EMITIR un token (iat/exp),
pero PyJWT verifica el vencimiento contra el reloj real del sistema por
diseño: es lo correcto para una credencial firmada que un cliente puede
presentar en cualquier momento futuro real. Por eso la prueba de expiracion
usa una duracion negativa en vez de una fecha fija: es determinista sin
importar la fecha real en que corra la prueba.
"""

from __future__ import annotations

import pytest

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import SesionExpiradaError, SesionInvalidaError
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.seguridad.gestor_sesion_jwt import GestorSesionJwt
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

_CLAVE_FIRMA = "clave-de-prueba-suficientemente-larga-32b"


def _usuario_prueba() -> Usuario:
    return Usuario(
        id=1,
        nombre_usuario="ana.analista",
        nombres="Ana Analista",
        hash_clave="no-usado-en-esta-prueba",
        activo=True,
        roles=frozenset({NombreRol.ANALISTA}),
    )


def prueba_hash_y_verificacion_de_clave_correcta() -> None:
    verificador = VerificadorClaveBcrypt()
    hash_clave = verificador.generar_hash("clave-secreta-123")
    assert hash_clave != "clave-secreta-123"
    assert verificador.verificar("clave-secreta-123", hash_clave)


def prueba_verificacion_de_clave_incorrecta() -> None:
    verificador = VerificadorClaveBcrypt()
    hash_clave = verificador.generar_hash("clave-secreta-123")
    assert not verificador.verificar("otra-clave", hash_clave)


def prueba_token_emitido_se_verifica_con_el_usuario_correcto() -> None:
    gestor = GestorSesionJwt(clave_firma=_CLAVE_FIRMA, duracion_minutos=30, reloj=RelojSistema())
    usuario = _usuario_prueba()

    token = gestor.emitir(usuario)
    carga = gestor.verificar(token)

    assert carga.usuario_id == 1
    assert carga.nombre_usuario == "ana.analista"
    assert carga.roles == frozenset({NombreRol.ANALISTA})


def prueba_token_expirado_se_rechaza() -> None:
    gestor = GestorSesionJwt(clave_firma=_CLAVE_FIRMA, duracion_minutos=-1, reloj=RelojSistema())
    token = gestor.emitir(_usuario_prueba())

    with pytest.raises(SesionExpiradaError):
        gestor.verificar(token)


def prueba_token_con_firma_distinta_se_rechaza() -> None:
    reloj = RelojSistema()
    emisor = GestorSesionJwt(
        clave_firma="clave-de-prueba-a-suficientemente-larga", duracion_minutos=30, reloj=reloj
    )
    verificador = GestorSesionJwt(
        clave_firma="clave-de-prueba-b-suficientemente-larga", duracion_minutos=30, reloj=reloj
    )

    token = emisor.emitir(_usuario_prueba())
    with pytest.raises(SesionInvalidaError):
        verificador.verificar(token)


def prueba_token_con_texto_arbitrario_se_rechaza() -> None:
    gestor = GestorSesionJwt(clave_firma=_CLAVE_FIRMA, duracion_minutos=30, reloj=RelojSistema())
    with pytest.raises(SesionInvalidaError):
        gestor.verificar("esto-no-es-un-token-jwt")
