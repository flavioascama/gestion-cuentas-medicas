"""Puertos del contexto de sesiones asistidas (Seccion 5.2, 8.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.dominio.plataformas.valores import SesionPlataforma


class ErrorSesionPlataforma(Exception):
    pass


class ErrorSesionNoEncontrada(ErrorSesionPlataforma):
    pass


class ErrorPlataformaInvalida(ErrorSesionPlataforma):
    pass


class ErrorSesionFallida(ErrorSesionPlataforma):
    """La lanza `AsistenteSesionPlataforma.iniciar_sesion` cuando la
    sesion termina FALLIDA (credenciales invalidas o tres intentos de
    CAPTCHA agotados, Seccion 8.4 punto 5) o cuando se agota el tiempo
    limite de espera de la respuesta humana."""


class RepositorioSesionPlataforma(Protocol):
    async def crear_solicitud(self, plataforma: str, solicitada_por: str) -> int:
        """Fila nueva en SOLICITADA (Seccion 8.4, punto 1). Devuelve su id."""
        ...

    async def obtener(self, sesion_id: int) -> SesionPlataforma | None:
        """None si no existe esa sesion."""
        ...

    async def listar(self, plataforma: str | None) -> list[SesionPlataforma]:
        """Mas reciente primero (Fase 18, `GET /plataformas/sesiones`).
        `plataforma=None` lista de todas las plataformas."""
        ...

    async def obtener_activa(self, plataforma: str) -> SesionPlataforma | None:
        """None si no hay ninguna sesion ACTIVA y vigente (`expira_en` en
        el futuro) para esa plataforma (Seccion 8.4, punto 6). Si
        encuentra una ACTIVA ya vencida, la deja EXPIRADA antes de
        devolver None."""
        ...

    async def expirar_activas(self, plataforma: str) -> None:
        """Deja EXPIRADA la sesion ACTIVA de la plataforma: el robot
        comprobo que la plataforma ya no la acepta, aunque su plazo no
        haya vencido (2026-11-18). Asi se puede pedir otra."""
        ...

    async def registrar_captcha(self, sesion_id: int, imagen: bytes) -> None:
        """Pasa a ESPERANDO_CAPTCHA (Seccion 8.4, punto 2)."""
        ...

    async def registrar_respuesta(self, sesion_id: int, respuesta: str) -> None:
        """Pasa a CAPTCHA_RESPONDIDO (Seccion 8.4, punto 3)."""
        ...

    async def activar(self, sesion_id: int, expira_en: datetime) -> None:
        """Pasa a ACTIVA, fija `activa_desde`/`expira_en` y borra
        `respuesta_captcha` (Seccion 8.4, punto 4: 'borra la respuesta
        del CAPTCHA de la base de datos')."""
        ...

    async def reintentar_captcha(self, sesion_id: int, imagen: bytes) -> None:
        """Seccion 8.4, punto 5: respuesta incorrecta -- nueva imagen,
        vuelve a ESPERANDO_CAPTCHA, incrementa `intentos`, borra la
        respuesta anterior."""
        ...

    async def marcar_fallida(self, sesion_id: int, motivo: str) -> None: ...


class AsistenteSesionPlataforma(Protocol):
    """Puerto sobre el robot RPA que conduce el ingreso asistido (Seccion
    8.4, puntos 2 a 5). La unica implementacion vive en
    sistema/automatizacion/trabajador/robots/, un proceso separado
    (AD-02) que usa Playwright -- el dominio no lo sabe, solo pide
    'iniciar esta sesion' y espera que quede ACTIVA o que se lance
    `ErrorSesionFallida`.

    La implementacion necesita leer y escribir `sesion_plataforma`
    mientras conduce el flujo (publicar la imagen, esperar la respuesta),
    asi que recibe su propio `RepositorioSesionPlataforma` inyectado; el
    caso de uso que la llama solo registra el evento y la medicion del
    resultado final."""

    async def iniciar_sesion(self, sesion_id: int, plataforma: str) -> None:
        """Abre la pagina de ingreso, completa usuario/contrasena,
        publica la imagen del CAPTCHA (ESPERANDO_CAPTCHA) y espera la
        respuesta humana hasta el tiempo limite configurado. Si acierta,
        guarda `storage_state` cifrado y deja la sesion ACTIVA. Si agota
        los tres intentos o el tiempo limite, deja la sesion FALLIDA y
        lanza `ErrorSesionFallida`."""
        ...
