"""Fixtures compartidas de prueba: base de datos SQLite en memoria.

Estas pruebas de integracion via HTTP usan SQLite en memoria para ser
rapidas y no requerir Docker en cada corrida (decision documentada en
docs/DECISIONES.md). Las pruebas de integracion de la Seccion 12.2, sobre la
composicion completa de contenedores, se ejecutan aparte, contra Postgres
real.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from itertools import count
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia import modelos_acceso, todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

# Mayuscula, minuscula y digito: cumple el control C-01 (Seccion 5.2.7),
# minimo 12 caracteres -- app.dominio.acceso.valores.validar_politica_clave.
_CLAVE_PRUEBA = "Clave-Valida-123"


@pytest_asyncio.fixture
async def fabrica_sesiones() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    motor = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(bind=motor, expire_on_commit=False)
    async with fabrica() as sesion:
        sesion.add_all(modelos_acceso.RolModelo(nombre=rol.value) for rol in NombreRol)
        await sesion.commit()

    yield fabrica
    await motor.dispose()


@pytest_asyncio.fixture
async def cliente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    from app.api.main import app
    from app.infraestructura.persistencia.base import obtener_sesion

    async def _sobreescribir_sesion() -> AsyncGenerator[AsyncSession, None]:
        async with fabrica_sesiones() as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion] = _sobreescribir_sesion
    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://prueba") as cliente_http:
        yield cliente_http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def token_para_rol(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> Callable[[NombreRol], Awaitable[str]]:
    """Crea un usuario nuevo con el rol pedido e inicia sesion. Pensada
    para pruebas de autorizacion por ruta (Seccion 13, Fase 18): cada
    llamada usa un nombre de usuario distinto (el contador) para poder
    pedir varios roles en la misma prueba sin chocar."""

    contador = count()

    async def _crear(rol: NombreRol) -> str:
        nombre_usuario = f"{rol.value}.prueba.{next(contador)}"
        async with fabrica_sesiones() as sesion:
            registrar = RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt())
            await registrar.ejecutar(
                nombre_usuario=nombre_usuario,
                clave=_CLAVE_PRUEBA,
                nombres=nombre_usuario,
                roles=frozenset({rol}),
            )
        respuesta = await cliente.post(
            "/auth/sesion", json={"nombre_usuario": nombre_usuario, "clave": _CLAVE_PRUEBA}
        )
        assert respuesta.status_code == 200
        return str(respuesta.json()["token"])

    return _crear


def pytest_html_report_title(report: Any) -> None:  # pragma: no cover
    report.title = "Sistema OE1 -- resultado de la suite (datos sinteticos)"


def pytest_configure(config: Any) -> None:  # pragma: no cover
    """Seccion 13 (Fase 20): "todos los reportes incluyen una cabecera
    que declara datos sinteticos y entorno de prueba". Esta suite
    (SQLite en memoria) no habla con ningun simulador, asi que a
    diferencia de los CSV/JSON de reportes/, no hay una latencia
    artificial que declarar aqui -- solo pytest-html/pytest-cov, activos
    unicamente cuando alguien pasa --html/--cov (Seccion 13 no forma
    parte de la corrida rapida de cada guardado)."""

    if hasattr(config, "_metadata"):
        config._metadata["Datos"] = "Sinteticos"
        config._metadata["Entorno"] = "Prueba (SQLite en memoria, sin Docker)"
