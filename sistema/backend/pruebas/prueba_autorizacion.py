"""Pruebas de integracion de autenticacion y autorizacion por rol (Seccion 12.2,
fila 'Autorizacion'): entregable de la Fase 2 segun la Seccion 13.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol, Usuario
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

_CLAVE = "Clave-Valida-123"


async def _crear_usuario(
    fabrica_sesiones: async_sessionmaker[AsyncSession], nombre_usuario: str, rol: NombreRol
) -> Usuario:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioUsuariosSql(sesion)
        registrar = RegistrarUsuario(repositorio, VerificadorClaveBcrypt())
        return await registrar.ejecutar(
            nombre_usuario=nombre_usuario,
            clave=_CLAVE,
            nombres=nombre_usuario.title(),
            roles=frozenset({rol}),
        )


@pytest_asyncio.fixture
async def token_administrador(
    fabrica_sesiones: async_sessionmaker[AsyncSession], cliente: AsyncClient
) -> AsyncGenerator[str, None]:
    await _crear_usuario(fabrica_sesiones, "admin.prueba", NombreRol.ADMINISTRADOR)
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "admin.prueba", "clave": _CLAVE}
    )
    assert respuesta.status_code == 200
    yield respuesta.json()["token"]


async def prueba_login_correcto_devuelve_token(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> None:
    await _crear_usuario(fabrica_sesiones, "ana.analista", NombreRol.ANALISTA)

    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "ana.analista", "clave": _CLAVE}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "bearer"
    assert len(cuerpo["token"]) > 0


async def prueba_login_con_clave_incorrecta_devuelve_401(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> None:
    await _crear_usuario(fabrica_sesiones, "ana.analista", NombreRol.ANALISTA)

    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "ana.analista", "clave": "equivocada"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "CREDENCIALES_INVALIDAS"


async def prueba_login_con_usuario_inexistente_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "no.existe", "clave": "cualquiera"}
    )
    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "CREDENCIALES_INVALIDAS"


async def prueba_ruta_protegida_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/usuarios")
    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "SESION_REQUERIDA"


async def prueba_ruta_protegida_con_token_invalido_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/usuarios", headers={"Authorization": "Bearer token-invalido"})
    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "SESION_INVALIDA"


async def prueba_ruta_de_administrador_con_rol_incorrecto_devuelve_403(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> None:
    await _crear_usuario(fabrica_sesiones, "ana.analista", NombreRol.ANALISTA)
    inicio = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "ana.analista", "clave": _CLAVE}
    )
    token = inicio.json()["token"]

    respuesta = await cliente.get("/usuarios", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "ROL_NO_AUTORIZADO"


async def prueba_administrador_puede_listar_usuarios(
    cliente: AsyncClient, token_administrador: str
) -> None:
    respuesta = await cliente.get(
        "/usuarios", headers={"Authorization": f"Bearer {token_administrador}"}
    )

    assert respuesta.status_code == 200
    nombres = [usuario["nombre_usuario"] for usuario in respuesta.json()]
    assert "admin.prueba" in nombres


async def prueba_administrador_puede_crear_usuario(
    cliente: AsyncClient, token_administrador: str
) -> None:
    respuesta = await cliente.post(
        "/usuarios",
        headers={"Authorization": f"Bearer {token_administrador}"},
        json={
            "nombre_usuario": "carla.auditora",
            "clave": "Clave-Valida-456",
            "nombres": "Carla Auditora",
            "roles": ["auditor"],
        },
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["nombre_usuario"] == "carla.auditora"
    assert cuerpo["roles"] == ["auditor"]
    assert "hash_clave" not in cuerpo
    assert "clave" not in cuerpo


async def prueba_crear_usuario_duplicado_devuelve_409(
    cliente: AsyncClient, token_administrador: str
) -> None:
    solicitud = {
        "nombre_usuario": "carla.auditora",
        "clave": "Clave-Valida-456",
        "nombres": "Carla Auditora",
        "roles": ["auditor"],
    }
    encabezados = {"Authorization": f"Bearer {token_administrador}"}
    primera = await cliente.post("/usuarios", headers=encabezados, json=solicitud)
    assert primera.status_code == 201

    segunda = await cliente.post("/usuarios", headers=encabezados, json=solicitud)
    assert segunda.status_code == 409
    assert segunda.json()["codigo"] == "NOMBRE_USUARIO_DUPLICADO"


async def prueba_crear_usuario_como_no_administrador_devuelve_403(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> None:
    await _crear_usuario(fabrica_sesiones, "beto.jefe", NombreRol.JEFE)
    inicio = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "beto.jefe", "clave": _CLAVE}
    )
    token = inicio.json()["token"]

    respuesta = await cliente.post(
        "/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre_usuario": "otro.usuario",
            "clave": "Clave-Valida-456",
            "nombres": "Otro Usuario",
            "roles": ["analista"],
        },
    )

    assert respuesta.status_code == 403


async def prueba_cerrar_sesion_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    respuesta = await cliente.delete("/auth/sesion")
    assert respuesta.status_code == 401


async def prueba_cerrar_sesion_con_cualquier_rol_autenticado_devuelve_204(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> None:
    await _crear_usuario(fabrica_sesiones, "ana.analista", NombreRol.ANALISTA)
    inicio = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "ana.analista", "clave": _CLAVE}
    )
    token = inicio.json()["token"]

    respuesta = await cliente.delete("/auth/sesion", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 204


# --- Clave temporal (2026-11-18) ------------------------------------------


async def prueba_con_clave_temporal_solo_se_puede_cambiarla(
    cliente: AsyncClient, token_administrador: str
) -> None:
    admin = {"Authorization": f"Bearer {token_administrador}"}
    creado = await cliente.post(
        "/usuarios",
        headers=admin,
        json={
            "nombre_usuario": "nueva.analista",
            "clave": _CLAVE,
            "nombres": "Nueva Analista",
            "roles": ["analista"],
        },
    )
    assert creado.status_code == 201
    ingreso = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "nueva.analista", "clave": _CLAVE}
    )
    temporal = {"Authorization": f"Bearer {ingreso.json()['token']}"}

    # Con la clave que puso el administrador no se opera.
    bloqueada = await cliente.get("/cuentas", headers=temporal)
    assert bloqueada.status_code == 403
    assert bloqueada.json()["codigo"] == "CAMBIO_DE_CLAVE_REQUERIDO"

    equivocada = await cliente.put(
        "/auth/clave",
        headers=temporal,
        json={"clave_actual": "Otra-Clave-0000", "clave_nueva": "Propia-Clave-2027"},
    )
    assert equivocada.status_code == 400
    assert equivocada.json()["codigo"] == "CLAVE_ACTUAL_INCORRECTA"

    cambio = await cliente.put(
        "/auth/clave",
        headers=temporal,
        json={"clave_actual": _CLAVE, "clave_nueva": "Propia-Clave-2027"},
    )
    assert cambio.status_code == 200
    propia = {"Authorization": f"Bearer {cambio.json()['token']}"}

    assert (await cliente.get("/cuentas", headers=propia)).status_code == 200
    # La credencial con la que se hizo el cambio queda revocada.
    assert (await cliente.get("/cuentas", headers=temporal)).status_code == 401
    # Y la clave anterior ya no sirve para ingresar.
    viejo = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "nueva.analista", "clave": _CLAVE}
    )
    assert viejo.status_code == 401
