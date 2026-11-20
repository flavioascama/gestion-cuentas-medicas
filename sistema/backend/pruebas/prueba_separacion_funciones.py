"""Separacion de funciones (2026-11-19): la observacion asignada la
responde su responsable, nadie cambia sus propios roles y la anulacion no
la aprueba quien la pidio. Con los falsos de las pruebas de cada area."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.dominio.acceso.casos_uso import ActualizarUsuario
from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import NoPuedeCambiarSusRolesError
from app.dominio.cierre.casos_uso import ResolverSolicitudAnulacion, SolicitarAnulacion
from app.dominio.cierre.errores import ErrorAnulacionPropia
from app.dominio.observaciones.casos_uso import ResponderObservacion
from app.dominio.observaciones.errores import ErrorObservacionDeOtroResponsable
from app.dominio.observaciones.valores import (
    DatosNuevaObservacion,
    Naturaleza,
    Respondedor,
)
from pruebas import prueba_casos_uso_cierre as cierre
from pruebas import prueba_casos_uso_observaciones as obs
from pruebas.prueba_acceso_casos_uso import RepositorioUsuariosFalso

# --- 2. la observacion asignada la responde su responsable -----------------


async def _observacion(
    responsable_usuario_id: int | None,
) -> tuple[ResponderObservacion, int, obs._RegistroEventosFalso]:
    repositorio = obs._ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=obs._AHORA,
        )
    )
    if responsable_usuario_id is not None:
        await repositorio.reasignar(
            observacion_id, Naturaleza.ADMINISTRATIVA, NombreRol.ANALISTA, responsable_usuario_id
        )
    eventos = obs._RegistroEventosFalso()
    caso_uso = ResponderObservacion(
        repositorio=repositorio,
        estado_cuenta=obs._EstadoCuentaFalso({1: "GLOSADA"}),
        observabilidad=obs._observabilidad(eventos),
        reloj=obs._RelojFijo(),
    )
    return caso_uso, observacion_id, eventos


@pytest.mark.parametrize("respondedor", [Respondedor(8, "otro.analista"), None])
async def prueba_otro_no_responde_una_observacion_asignada(
    respondedor: Respondedor | None,
) -> None:
    caso_uso, observacion_id, eventos = await _observacion(responsable_usuario_id=7)
    with pytest.raises(ErrorObservacionDeOtroResponsable):
        await caso_uso.ejecutar(
            observacion_id, "Respuesta.", None, "otro.analista", respondedor=respondedor
        )
    assert eventos.eventos == []


async def prueba_el_responsable_asignado_responde() -> None:
    caso_uso, observacion_id, eventos = await _observacion(responsable_usuario_id=7)
    await caso_uso.ejecutar(
        observacion_id,
        "Respuesta.",
        None,
        "ana.analista",
        respondedor=Respondedor(7, "ana.analista"),
    )
    assert eventos.eventos[0].tipo_evento == "OBSERVACION_RESPONDIDA"
    assert eventos.eventos[0].usuario_origen == "ana.analista"


async def prueba_sin_responsable_asignado_responde_quien_tiene_el_rol() -> None:
    caso_uso, observacion_id, eventos = await _observacion(responsable_usuario_id=None)
    await caso_uso.ejecutar(
        observacion_id, "Respuesta.", None, "otro.analista", respondedor=Respondedor(8, "otro")
    )
    assert eventos.eventos[0].tipo_evento == "OBSERVACION_RESPONDIDA"


# --- 3. nadie cambia sus propios roles --------------------------------------


async def _administradora() -> tuple[RepositorioUsuariosFalso, Usuario]:
    repositorio = RepositorioUsuariosFalso()
    usuario = await repositorio.crear(
        Usuario(
            id=None,
            nombre_usuario="adm.prueba",
            nombres="Administradora",
            hash_clave="x",
            activo=True,
            roles=frozenset({NombreRol.ADMINISTRADOR}),
        )
    )
    return repositorio, usuario


@pytest.mark.parametrize(
    "cambio",
    [
        {"roles": frozenset({NombreRol.ADMINISTRADOR, NombreRol.JEFE})},
        {"roles": frozenset({NombreRol.ANALISTA})},
        {"activo": False},
    ],
)
async def prueba_el_administrador_no_cambia_sus_roles_ni_se_desactiva(
    cambio: dict[str, object],
) -> None:
    repositorio, usuario = await _administradora()
    assert usuario.id is not None
    with pytest.raises(NoPuedeCambiarSusRolesError):
        await ActualizarUsuario(repositorio).ejecutar(usuario.id, actor="adm.prueba", **cambio)  # type: ignore[arg-type]
    actual = await repositorio.obtener_por_id(usuario.id)
    assert actual is not None and actual.roles == usuario.roles and actual.activo


async def prueba_el_administrador_si_cambia_su_nombre() -> None:
    repositorio, usuario = await _administradora()
    assert usuario.id is not None
    actualizado = await ActualizarUsuario(repositorio).ejecutar(
        usuario.id,
        nombres="Administradora General",
        # Los mismos roles y estado de siempre no son un cambio.
        roles=usuario.roles,
        activo=True,
        actor="adm.prueba",
    )
    assert actualizado.nombres == "Administradora General"


async def prueba_otro_administrador_si_cambia_sus_roles() -> None:
    repositorio, usuario = await _administradora()
    assert usuario.id is not None
    actualizado = await ActualizarUsuario(repositorio).ejecutar(
        usuario.id, roles=frozenset({NombreRol.JEFE}), actor="otro.administrador"
    )
    assert actualizado.roles == frozenset({NombreRol.JEFE})


# --- 4. la anulacion no la aprueba quien la pidio ---------------------------


async def _solicitud() -> tuple[cierre._SolicitudesAnulacionFalso, int]:
    repositorio = cierre._SolicitudesAnulacionFalso()
    solicitud_id = await SolicitarAnulacion(
        repositorio=repositorio,
        estado_cuenta=cierre._EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=cierre._observabilidad(cierre._RegistroEventosFalso()),
        reloj=cierre._RelojFijo(),
    ).ejecutar(1, "paciente no se presento", actor="jefa.doble")
    return repositorio, solicitud_id


def _resolver(
    repositorio: cierre._SolicitudesAnulacionFalso, estado_cuenta: cierre._EstadoCuentaFalso
) -> ResolverSolicitudAnulacion:
    return ResolverSolicitudAnulacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=cierre._observabilidad(cierre._RegistroEventosFalso()),
        reloj=cierre._RelojFijo(),
    )


async def prueba_quien_solicito_la_anulacion_no_la_aprueba() -> None:
    repositorio, solicitud_id = await _solicitud()
    estado_cuenta = cierre._EstadoCuentaFalso({1: "FACTURADA"})
    with pytest.raises(ErrorAnulacionPropia):
        await _resolver(repositorio, estado_cuenta).ejecutar(
            solicitud_id, aprobada=True, actor="jefa.doble"
        )
    assert estado_cuenta.estados[1] == "FACTURADA"
    assert repositorio.filas[solicitud_id].estado == "PENDIENTE"

    # Otra persona si la aprueba.
    estado = await _resolver(repositorio, estado_cuenta).ejecutar(
        solicitud_id, aprobada=True, actor="otra.jefa"
    )
    assert estado == "ANULADA"


async def prueba_quien_solicito_la_anulacion_si_puede_rechazarla() -> None:
    repositorio, solicitud_id = await _solicitud()
    estado_cuenta = cierre._EstadoCuentaFalso({1: "FACTURADA"})
    resultado = await _resolver(repositorio, estado_cuenta).ejecutar(
        solicitud_id, aprobada=False, actor="jefa.doble"
    )
    assert resultado is None
    assert repositorio.filas[solicitud_id].estado == "RECHAZADA"


async def prueba_ruta_responde_403_al_cambiar_sus_propios_roles(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ADMINISTRADOR)
    cabeceras = {"Authorization": f"Bearer {token}"}
    usuarios = (await cliente.get("/usuarios", headers=cabeceras)).json()
    propio = next(u for u in usuarios if u["nombre_usuario"].startswith("administrador."))

    respuesta = await cliente.patch(
        f"/usuarios/{propio['id']}", json={"roles": ["administrador", "jefe"]}, headers=cabeceras
    )
    assert respuesta.status_code == 403
    assert "NO_PUEDE_CAMBIAR_SUS_ROLES" in respuesta.text

    respuesta = await cliente.patch(
        f"/usuarios/{propio['id']}", json={"nombres": "Otro Nombre"}, headers=cabeceras
    )
    assert respuesta.status_code == 200
