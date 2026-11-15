"""Motor y sesion de SQLAlchemy 2.0, en modo asincrono con asyncpg.

Este modulo es infraestructura pura: el dominio no lo importa (Seccion 5.2).
Los modelos concretos (usuario, cuenta_medica, lote_facturacion, etc.) se
agregan en las fases 2, 7 y 8, cada uno en su propio archivo bajo
`persistencia/`, todos heredando de `Base`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.compartido.configuracion import obtener_configuracion


class Base(DeclarativeBase):
    """Clase base declarativa comun a todos los modelos del backend."""


_configuracion = obtener_configuracion()

motor = create_async_engine(_configuracion.url_base_datos, pool_pre_ping=True)

FabricaSesiones = async_sessionmaker(bind=motor, expire_on_commit=False)


async def obtener_sesion() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: una sesion por solicitud."""

    async with FabricaSesiones() as sesion:
        yield sesion
