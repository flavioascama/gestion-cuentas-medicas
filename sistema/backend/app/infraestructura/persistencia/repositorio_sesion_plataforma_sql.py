"""Adaptador de RepositorioSesionPlataforma (Seccion 8.4, Fase 15)."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.plataformas.puertos import RepositorioSesionPlataforma
from app.dominio.plataformas.valores import SesionPlataforma
from app.infraestructura.persistencia.modelos_plataformas import SesionPlataformaModelo


def _a_valor(fila: SesionPlataformaModelo) -> SesionPlataforma:
    return SesionPlataforma(
        id=fila.id,
        plataforma=fila.plataforma,
        estado=fila.estado,
        solicitada_por=fila.solicitada_por,
        creada_en=fila.creada_en,
        imagen_captcha=fila.imagen_captcha,
        respuesta_captcha=fila.respuesta_captcha,
        activa_desde=fila.activa_desde,
        expira_en=fila.expira_en,
        intentos=fila.intentos,
        motivo=fila.motivo,
    )


class RepositorioSesionPlataformaSql(RepositorioSesionPlataforma):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear_solicitud(self, plataforma: str, solicitada_por: str) -> int:
        fila = SesionPlataformaModelo(
            plataforma=plataforma, estado="SOLICITADA", solicitada_por=solicitada_por, intentos=0
        )
        self._sesion.add(fila)
        await self._sesion.flush()
        id_creado = fila.id
        await self._sesion.commit()
        return id_creado

    async def obtener(self, sesion_id: int) -> SesionPlataforma | None:
        fila = await self._sesion.get(SesionPlataformaModelo, sesion_id)
        return _a_valor(fila) if fila is not None else None

    async def listar(self, plataforma: str | None) -> list[SesionPlataforma]:
        consulta = sa.select(SesionPlataformaModelo)
        if plataforma is not None:
            consulta = consulta.where(SesionPlataformaModelo.plataforma == plataforma)
        consulta = consulta.order_by(SesionPlataformaModelo.creada_en.desc())
        resultado = await self._sesion.execute(consulta)
        filas = resultado.scalars().all()

        # Mismo autosaneamiento que `obtener_activa`: una fila ACTIVA cuyo
        # expira_en ya paso no deja de estarlo sola en la base -- nada la
        # reescribe hasta que algo la lee. Sin esto, el listado (el que usa
        # el frontend para decidir si mostrar "Iniciar sesion") seguiria
        # devolviendo ACTIVA indefinidamente y el boton de sesion asistida
        # quedaria oculto aunque el trabajo ya haya caido en REQUIERE_SESION.
        ahora = datetime.now(UTC)
        huso_saneado = False
        for fila in filas:
            if fila.estado != "ACTIVA" or fila.expira_en is None:
                continue
            expira_en = fila.expira_en
            if expira_en.tzinfo is None:
                expira_en = expira_en.replace(tzinfo=UTC)
            if expira_en <= ahora:
                fila.estado = "EXPIRADA"
                huso_saneado = True
        if huso_saneado:
            await self._sesion.commit()

        return [_a_valor(fila) for fila in filas]

    async def obtener_activa(self, plataforma: str) -> SesionPlataforma | None:
        resultado = await self._sesion.execute(
            sa.select(SesionPlataformaModelo)
            .where(
                SesionPlataformaModelo.plataforma == plataforma,
                SesionPlataformaModelo.estado == "ACTIVA",
            )
            .order_by(SesionPlataformaModelo.activa_desde.desc())
            .limit(1)
        )
        fila = resultado.scalar_one_or_none()
        if fila is None:
            return None

        ahora = datetime.now(UTC)
        # SQLite (usado en las pruebas, ver pruebas/conftest.py) no
        # conserva el huso horario en columnas DateTime(timezone=True):
        # lo que vuelve de la base queda "naive" aunque siempre se
        # escriba en UTC. Postgres (produccion y Docker) si lo conserva,
        # asi que aqui no hace falta convertir nada mas.
        expira_en = fila.expira_en
        if expira_en is not None and expira_en.tzinfo is None:
            expira_en = expira_en.replace(tzinfo=UTC)
        if expira_en is not None and expira_en <= ahora:
            fila.estado = "EXPIRADA"
            await self._sesion.commit()
            return None
        return _a_valor(fila)

    async def registrar_captcha(self, sesion_id: int, imagen: bytes) -> None:
        await self._sesion.execute(
            sa.update(SesionPlataformaModelo)
            .where(SesionPlataformaModelo.id == sesion_id)
            .values(estado="ESPERANDO_CAPTCHA", imagen_captcha=imagen)
        )
        await self._sesion.commit()

    async def registrar_respuesta(self, sesion_id: int, respuesta: str) -> None:
        await self._sesion.execute(
            sa.update(SesionPlataformaModelo)
            .where(SesionPlataformaModelo.id == sesion_id)
            .values(estado="CAPTCHA_RESPONDIDO", respuesta_captcha=respuesta)
        )
        await self._sesion.commit()

    async def activar(self, sesion_id: int, expira_en: datetime) -> None:
        await self._sesion.execute(
            sa.update(SesionPlataformaModelo)
            .where(SesionPlataformaModelo.id == sesion_id)
            .values(
                estado="ACTIVA",
                activa_desde=sa.func.now(),
                expira_en=expira_en,
                respuesta_captcha=None,
                imagen_captcha=None,
            )
        )
        await self._sesion.commit()

    async def reintentar_captcha(self, sesion_id: int, imagen: bytes) -> None:
        await self._sesion.execute(
            sa.update(SesionPlataformaModelo)
            .where(SesionPlataformaModelo.id == sesion_id)
            .values(
                estado="ESPERANDO_CAPTCHA",
                imagen_captcha=imagen,
                respuesta_captcha=None,
                intentos=SesionPlataformaModelo.intentos + 1,
            )
        )
        await self._sesion.commit()

    async def marcar_fallida(self, sesion_id: int, motivo: str) -> None:
        await self._sesion.execute(
            sa.update(SesionPlataformaModelo)
            .where(SesionPlataformaModelo.id == sesion_id)
            .values(estado="FALLIDA", motivo=motivo[:500])
        )
        await self._sesion.commit()
