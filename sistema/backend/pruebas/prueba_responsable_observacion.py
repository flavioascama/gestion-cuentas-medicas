"""Pruebas de a quien se puede asignar una observacion (CU-09, 2026-11-18),
con los mismos falsos de prueba_casos_uso_observaciones."""

from __future__ import annotations

import pytest

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.observaciones.casos_uso import (
    AsignarResponsableObservacion,
    ListarResponsablesPosibles,
)
from app.dominio.observaciones.errores import ErrorResponsableNoValido
from app.dominio.observaciones.valores import DatosNuevaObservacion, Naturaleza
from pruebas.prueba_casos_uso_observaciones import (
    _AHORA,
    _observabilidad,
    _ObservacionesFalso,
    _RegistroEventosFalso,
)

# --- Responsable de una observacion (2026-11-18) --------------------------


class _UsuariosFalso:
    """Solo lo que usan estos casos de uso de RepositorioUsuarios."""

    def __init__(self, usuarios: list[Usuario]) -> None:
        self._usuarios = usuarios

    async def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        return next((u for u in self._usuarios if u.id == usuario_id), None)

    async def listar(self) -> list[Usuario]:
        return self._usuarios


def _usuario(usuario_id: int, rol: NombreRol, activo: bool = True) -> Usuario:
    return Usuario(
        id=usuario_id,
        nombre_usuario=f"usuario.{usuario_id}",
        nombres=f"Usuario {usuario_id}",
        hash_clave="x",
        activo=activo,
        roles=frozenset({rol}),
    )


_PERSONAS = [
    _usuario(1, NombreRol.ANALISTA),
    _usuario(2, NombreRol.AUDITOR),
    _usuario(3, NombreRol.ANALISTA, activo=False),
    _usuario(4, NombreRol.TESORERIA),
]


async def prueba_solo_se_puede_asignar_a_quien_responde_observaciones() -> None:
    posibles = await ListarResponsablesPosibles(_UsuariosFalso(_PERSONAS)).ejecutar()  # type: ignore[arg-type]
    assert [u.id for u in posibles] == [1, 2]


@pytest.mark.parametrize("usuario_id", [2, 3, 4, 99])
async def prueba_el_responsable_debe_tener_el_rol_que_responde(usuario_id: int) -> None:
    # Observacion administrativa: responde un analista activo.
    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
        )
    )
    caso_uso = AsignarResponsableObservacion(
        repositorio,
        _observabilidad(_RegistroEventosFalso()),
        _UsuariosFalso(_PERSONAS),  # type: ignore[arg-type]
    )
    with pytest.raises(ErrorResponsableNoValido):
        await caso_uso.ejecutar(observacion_id, "jefa.prueba", usuario_id)

    await caso_uso.ejecutar(observacion_id, "jefa.prueba", 1)
    observacion = await repositorio.obtener(observacion_id)
    assert observacion is not None and observacion.responsable_usuario_id == 1
