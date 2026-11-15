"""Pruebas de RepositorioSesionPlataformaSql contra SQLite en memoria
(Seccion 8.4, 10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_plataformas import SesionPlataformaModelo
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)


async def prueba_crear_solicitud_queda_solicitada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")

    async with fabrica_sesiones() as sesion:
        fila = await sesion.get(SesionPlataformaModelo, sesion_id)
        assert fila is not None
        assert fila.estado == "SOLICITADA"
        assert fila.solicitada_por == "analista"
        assert fila.intentos == 0


async def prueba_obtener_activa_devuelve_none_sin_sesion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        assert await repositorio.obtener_activa("acredita_salud") is None


async def prueba_obtener_activa_encuentra_una_vigente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")
        expira_en = datetime.now(UTC) + timedelta(minutes=30)
        await repositorio.activar(sesion_id, expira_en)

        activa = await repositorio.obtener_activa("acredita_salud")
        assert activa is not None
        assert activa.id == sesion_id
        assert activa.estado == "ACTIVA"


async def prueba_obtener_activa_expira_una_vencida(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")
        expira_en = datetime.now(UTC) - timedelta(minutes=1)
        await repositorio.activar(sesion_id, expira_en)

        assert await repositorio.obtener_activa("acredita_salud") is None

    async with fabrica_sesiones() as sesion:
        fila = await sesion.get(SesionPlataformaModelo, sesion_id)
        assert fila is not None
        assert fila.estado == "EXPIRADA"


async def prueba_listar_sanea_una_activa_vencida(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """La fila mas reciente que devuelve `listar` es la que el frontend usa
    para decidir si mostrar "Iniciar sesion" (GestorSesionPlataforma): si
    quedara ACTIVA sin sanear, ese boton nunca aparece aunque el trabajo ya
    haya caido en REQUIERE_SESION, y el usuario se queda sin forma de
    reintentar (Seccion 8.4, punto 6)."""

    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")
        expira_en = datetime.now(UTC) - timedelta(minutes=1)
        await repositorio.activar(sesion_id, expira_en)

        listado = await repositorio.listar("acredita_salud")
        assert listado[0].id == sesion_id
        assert listado[0].estado == "EXPIRADA"

    async with fabrica_sesiones() as sesion:
        fila = await sesion.get(SesionPlataformaModelo, sesion_id)
        assert fila is not None
        assert fila.estado == "EXPIRADA"


async def prueba_registrar_captcha_y_reintentar(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")

        await repositorio.registrar_captcha(sesion_id, b"primera-imagen")
        primera = await repositorio.obtener(sesion_id)
        assert primera is not None
        assert primera.estado == "ESPERANDO_CAPTCHA"
        assert primera.imagen_captcha == b"primera-imagen"
        assert primera.intentos == 0

        await repositorio.registrar_respuesta(sesion_id, "ABCDE")
        respondida = await repositorio.obtener(sesion_id)
        assert respondida is not None
        assert respondida.estado == "CAPTCHA_RESPONDIDO"
        assert respondida.respuesta_captcha == "ABCDE"

        await repositorio.reintentar_captcha(sesion_id, b"segunda-imagen")
        segunda = await repositorio.obtener(sesion_id)
        assert segunda is not None
        assert segunda.estado == "ESPERANDO_CAPTCHA"
        assert segunda.imagen_captcha == b"segunda-imagen"
        assert segunda.respuesta_captcha is None
        assert segunda.intentos == 1


async def prueba_activar_borra_la_imagen_y_la_respuesta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")
        await repositorio.registrar_captcha(sesion_id, b"imagen")
        await repositorio.registrar_respuesta(sesion_id, "ABCDE")

        expira_en = datetime.now(UTC) + timedelta(minutes=30)
        await repositorio.activar(sesion_id, expira_en)

        activada = await repositorio.obtener(sesion_id)
        assert activada is not None
        assert activada.estado == "ACTIVA"
        assert activada.imagen_captcha is None
        assert activada.respuesta_captcha is None
        assert activada.activa_desde is not None


async def prueba_marcar_fallida(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioSesionPlataformaSql(sesion)
        sesion_id = await repositorio.crear_solicitud("acredita_salud", "analista")
        await repositorio.marcar_fallida(sesion_id, "Se agotaron los intentos de CAPTCHA.")

        fallida = await repositorio.obtener(sesion_id)
        assert fallida is not None
        assert fallida.estado == "FALLIDA"
        assert fallida.motivo == "Se agotaron los intentos de CAPTCHA."
