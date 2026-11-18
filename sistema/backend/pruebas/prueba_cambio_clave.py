"""Pruebas del cambio de clave propio y de la clave temporal que pone el
administrador (2026-11-18), con los mismos falsos de prueba_acceso_casos_uso."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.dominio.acceso.cambio_clave import CambiarClavePropia, ColaboradoresCambioClave
from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.errores import (
    ClaveActualIncorrectaError,
    ClaveDebilError,
    ClaveRepetidaError,
    CuentaBloqueadaError,
)
from app.dominio.acceso.puertos import CargaSesion
from pruebas.prueba_acceso_casos_uso import (
    _AHORA,
    _POLITICA_BLOQUEO,
    GestorSesionFalso,
    RegistroEventosFalso,
    RegistroRevocacionesFalso,
    RepositorioUsuariosFalso,
    VerificadorClaveFalso,
    _RelojFijo,
)


@pytest.fixture
def repositorio() -> RepositorioUsuariosFalso:
    return RepositorioUsuariosFalso()


@pytest.fixture
def verificador() -> VerificadorClaveFalso:
    return VerificadorClaveFalso()


# --- Cambio de clave propio (2026-11-18) ----------------------------------

_CLAVE_TEMPORAL = "Temporal-Clave-2026"
_CLAVE_PROPIA = "Propia-Clave-2027"


async def _con_clave_temporal(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> CargaSesion:
    registrar = RegistrarUsuario(repositorio, verificador, clave_temporal=True)
    usuario = await registrar.ejecutar(
        nombre_usuario="ana.analista",
        clave=_CLAVE_TEMPORAL,
        nombres="Ana",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    assert usuario.id is not None
    return CargaSesion(
        usuario_id=usuario.id,
        nombre_usuario=usuario.nombre_usuario,
        roles=usuario.roles,
        jti="jti-anterior",
        expira_en=_AHORA + timedelta(minutes=60),
        debe_cambiar_clave=True,
    )


def _cambiar_clave(
    repositorio: RepositorioUsuariosFalso,
    verificador: VerificadorClaveFalso,
    revocaciones: RegistroRevocacionesFalso | None = None,
    eventos: RegistroEventosFalso | None = None,
) -> CambiarClavePropia:
    colaboradores = ColaboradoresCambioClave(
        gestor_sesion=GestorSesionFalso(),
        registro_eventos=eventos or RegistroEventosFalso(),
        registro_revocaciones=revocaciones or RegistroRevocacionesFalso(),
    )
    return CambiarClavePropia(
        repositorio, verificador, colaboradores, _RelojFijo(_AHORA), _POLITICA_BLOQUEO
    )


async def prueba_la_clave_que_pone_el_administrador_obliga_a_cambiarla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    await _con_clave_temporal(repositorio, verificador)
    usuario = await repositorio.obtener_por_nombre_usuario("ana.analista")
    assert usuario is not None and usuario.debe_cambiar_clave


async def prueba_cambiar_la_clave_la_guarda_y_revoca_la_credencial_anterior(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    sesion = await _con_clave_temporal(repositorio, verificador)
    revocaciones = RegistroRevocacionesFalso()
    eventos = RegistroEventosFalso()
    caso_uso = _cambiar_clave(repositorio, verificador, revocaciones, eventos)

    token = await caso_uso.ejecutar(sesion, _CLAVE_TEMPORAL, _CLAVE_PROPIA)

    usuario = await repositorio.obtener_por_nombre_usuario("ana.analista")
    assert usuario is not None
    assert verificador.verificar(_CLAVE_PROPIA, usuario.hash_clave)
    assert not usuario.debe_cambiar_clave
    assert token == f"token::{usuario.id}"
    assert "jti-anterior" in revocaciones.revocados
    # La bitacora deja constancia del cambio, sin ningun dato de la clave.
    assert [(e.tipo_evento, e.datos) for e in eventos.eventos] == [("CLAVE_CAMBIADA", {})]


async def prueba_no_se_cambia_la_clave_sin_la_actual(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    sesion = await _con_clave_temporal(repositorio, verificador)
    caso_uso = _cambiar_clave(repositorio, verificador)

    with pytest.raises(ClaveActualIncorrectaError):
        await caso_uso.ejecutar(sesion, "Otra-Clave-0000", _CLAVE_PROPIA)

    usuario = await repositorio.obtener_por_nombre_usuario("ana.analista")
    assert usuario is not None
    assert verificador.verificar(_CLAVE_TEMPORAL, usuario.hash_clave)
    assert usuario.intentos_fallidos == 1


async def prueba_los_intentos_con_la_clave_actual_equivocada_bloquean_la_cuenta(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    sesion = await _con_clave_temporal(repositorio, verificador)
    caso_uso = _cambiar_clave(repositorio, verificador)
    for _ in range(_POLITICA_BLOQUEO.maximo_intentos_fallidos):
        with pytest.raises(ClaveActualIncorrectaError):
            await caso_uso.ejecutar(sesion, "Otra-Clave-0000", _CLAVE_PROPIA)

    # Bloqueada: ni con la clave correcta.
    with pytest.raises(CuentaBloqueadaError):
        await caso_uso.ejecutar(sesion, _CLAVE_TEMPORAL, _CLAVE_PROPIA)


async def prueba_la_clave_nueva_cumple_la_politica_y_es_distinta(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    sesion = await _con_clave_temporal(repositorio, verificador)
    caso_uso = _cambiar_clave(repositorio, verificador)

    with pytest.raises(ClaveRepetidaError):
        await caso_uso.ejecutar(sesion, _CLAVE_TEMPORAL, _CLAVE_TEMPORAL)
    with pytest.raises(ClaveDebilError):
        await caso_uso.ejecutar(sesion, _CLAVE_TEMPORAL, "sin-mayuscula-123")
