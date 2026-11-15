"""Fixtures de las pruebas de integracion "verdaderas" que promete
`pruebas/conftest.py` (Seccion 14.2 del plan v3 / Seccion 12.2 del v2):
"sobre la composicion completa de contenedores, incluidos los
simuladores". A diferencia de `pruebas/`, que usa SQLite en memoria para
ser rapida, esta carpeta se conecta al Postgres real del propio
contenedor (`URL_BASE_DATOS`, inyectada por docker-compose.yml) y al
backend real que ya esta corriendo en el mismo contenedor (`uvicorn` en
primer plano, puerto 8000) -- nunca ASGITransport.

No estan en `testpaths` de pyproject.toml (Seccion "pruebas" solamente):
se ejecutan aparte, a proposito, con
    docker compose exec backend uv run pytest pruebas_integracion/ -q
porque dependen de que el stack completo (postgres, backend, trabajador,
y los simuladores segun el escenario) ya este arriba -- no tiene sentido
que corran en cada guardado de archivo.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.compartido.configuracion import obtener_configuracion
from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

URL_BASE_BACKEND_REAL = "http://localhost:8000"
# Mayuscula, minuscula y digito: cumple el control C-01 (Seccion 5.2.7),
# minimo 12 caracteres -- app.dominio.acceso.valores.validar_politica_clave.
_CLAVE_PRUEBA = "Clave-Valida-123"


def _motor_de_prueba() -> AsyncEngine:
    """Motor propio por prueba, con NullPool: el motor global de
    `app.infraestructura.persistencia.base` es un singleton de modulo,
    creado (y atado a un event loop) la primera vez que algo lo usa.
    pytest-asyncio en modo auto crea un event loop nuevo POR PRUEBA, asi
    que reutilizar ese singleton entre pruebas revienta con "Future
    attached to a different loop" en cuanto la segunda prueba intenta
    usar una conexion que el pool abrio para la primera. NullPool evita
    que quede ninguna conexion viva para la siguiente prueba."""

    return create_async_engine(obtener_configuracion().url_base_datos, poolclass=NullPool)


@pytest_asyncio.fixture
async def sesion() -> AsyncGenerator[AsyncSession, None]:
    """Una sesion real por prueba, contra el Postgres del propio stack."""

    motor = _motor_de_prueba()
    fabrica = async_sessionmaker(bind=motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


@pytest_asyncio.fixture
async def cliente() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP contra el backend real (uvicorn en primer plano en
    este mismo contenedor), nunca ASGITransport: ejercita CORS, el ciclo
    de vida real de la conexion a Postgres y cualquier middleware."""

    async with AsyncClient(base_url=URL_BASE_BACKEND_REAL) as cliente_http:
        yield cliente_http


@pytest_asyncio.fixture
async def token_para_rol(
    cliente: AsyncClient,
) -> AsyncGenerator[Callable[[NombreRol], Awaitable[str]], None]:
    """Crea un usuario nuevo con el rol pedido, directo contra Postgres
    real, e inicia sesion contra la API real. Mismo patron que
    `pruebas/conftest.py::token_para_rol`, pero sin SQLite de por medio."""

    motor = _motor_de_prueba()
    fabrica = async_sessionmaker(bind=motor, expire_on_commit=False)

    async def _crear(rol: NombreRol) -> str:
        # uuid, no un contador: Postgres persiste entre corridas de la
        # suite (a diferencia de pruebas/conftest.py con SQLite en
        # memoria), asi que un contador que reinicia en cada fixture
        # nueva chocaria con nombres de usuario ya creados antes.
        nombre_usuario = f"integracion.{rol.value}.{uuid.uuid4().hex[:12]}"
        async with fabrica() as sesion_registro:
            registrar = RegistrarUsuario(
                RepositorioUsuariosSql(sesion_registro), VerificadorClaveBcrypt()
            )
            await registrar.ejecutar(
                nombre_usuario=nombre_usuario,
                clave=_CLAVE_PRUEBA,
                nombres=nombre_usuario,
                roles=frozenset({rol}),
            )
        respuesta = await cliente.post(
            "/auth/sesion", json={"nombre_usuario": nombre_usuario, "clave": _CLAVE_PRUEBA}
        )
        assert respuesta.status_code == 200, respuesta.text
        return str(respuesta.json()["token"])

    yield _crear
    await motor.dispose()


async def esperar_hasta[T](
    condicion: Callable[[], Awaitable[T | None]],
    *,
    tiempo_limite_segundos: float,
    intervalo_segundos: float = 0.5,
) -> T:
    """Sondea `condicion` hasta que devuelva un valor "verdadero" (no None
    y no falsy) o se agote el tiempo limite. Usado por los escenarios que
    dependen del trabajador/Playwright/un simulador -- nunca un `sleep`
    fijo, que seria fragil (muy corto: parpadea; muy largo: suite lenta)."""

    intentos = 0
    limite = asyncio.get_event_loop().time() + tiempo_limite_segundos
    while True:
        resultado = await condicion()
        if resultado:
            return resultado
        intentos += 1
        if asyncio.get_event_loop().time() >= limite:
            raise TimeoutError(
                f"Condicion no se cumplio tras {intentos} intentos en {tiempo_limite_segundos}s."
            )
        await asyncio.sleep(intervalo_segundos)
