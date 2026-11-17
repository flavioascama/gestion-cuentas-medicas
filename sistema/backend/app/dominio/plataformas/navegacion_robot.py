"""Navegacion visible del robot (pedido del usuario, 2026-11-17).

El robot trabaja en un navegador sin ventana, dentro del servidor: nadie ve
lo que hace. Con esta opcion, que solo el administrador activa, el robot
guarda una captura de su navegador en cada paso (ingreso, menu, formulario,
resultado) y quien opera el sistema la ve mientras el trabajo avanza.

Las capturas son evidencia del robot y muestran datos del asegurado: se
guardan cifradas (C-05, C-12), solo las ven los roles que ya trabajan con
esos datos (no el administrador, que solo activa la opcion) y cada consulta
queda en el historial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

CLAVE_OPCION_NAVEGACION_VISIBLE = "ROBOT_NAVEGACION_VISIBLE"
TIPO_EVENTO_OPCION_CAMBIADA = "NAVEGACION_ROBOT_OPCION_CAMBIADA"
TIPO_EVENTO_NAVEGACION_CONSULTADA = "NAVEGACION_ROBOT_CONSULTADA"
# Las capturas son para ver el trabajo en curso o reciente, no un archivo.
DIAS_RETENCION_PASOS = 7


@dataclass(frozen=True, slots=True)
class PasoCapturado:
    """Lo que el robot entrega al terminar un paso."""

    trabajo_id: int
    plataforma: str
    descripcion: str
    url: str
    captura: bytes


@dataclass(frozen=True, slots=True)
class PasoRobot:
    orden: int
    plataforma: str
    descripcion: str
    url: str
    capturado_en: datetime


@dataclass(frozen=True, slots=True)
class ActividadRobot:
    """Un trabajo del robot que dejo capturas."""

    trabajo_id: int
    tipo: str
    estado: str
    iniciado_en: datetime
    pasos: int


class RepositorioNavegacionRobot(Protocol):
    async def navegacion_visible(self) -> bool: ...

    async def fijar_navegacion_visible(self, activa: bool, actor: str) -> None: ...

    async def registrar_paso(self, paso: PasoCapturado) -> int:
        """Devuelve el numero de orden del paso dentro de su trabajo."""
        ...

    async def pasos(self, trabajo_id: int) -> list[PasoRobot]: ...

    async def captura(self, trabajo_id: int, orden: int) -> bytes | None: ...

    async def actividad(self, maximo: int) -> list[ActividadRobot]:
        """Trabajos con capturas, el mas reciente primero."""
        ...

    async def purgar_anteriores_a(self, limite: datetime) -> int: ...


def url_sin_consulta(url: str) -> str:
    """La direccion sin su cadena de consulta: ahi puede viajar el documento
    del asegurado, que no debe quedar en una columna sin cifrar."""
    return url.split("?", 1)[0].split("#", 1)[0]


def limite_de_retencion(reloj: Reloj) -> datetime:
    return reloj.ahora() - timedelta(days=DIAS_RETENCION_PASOS)


class CambiarNavegacionVisible:
    """Solo el administrador. Queda en el historial quien la activo o la
    apago."""

    def __init__(self, repositorio: RepositorioNavegacionRobot, eventos: RegistroEventos) -> None:
        self._repositorio = repositorio
        self._eventos = eventos

    async def ejecutar(self, activa: bool, actor: str, usuario_id: int) -> bool:
        await self._repositorio.fijar_navegacion_visible(activa, actor)
        await self._eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento=TIPO_EVENTO_OPCION_CAMBIADA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"activa": activa},
            )
        )
        return activa


class ObtenerCapturaPaso:
    """Devuelve la captura de un paso. Abrir la primera captura de un
    trabajo es abrir su navegacion: ese acceso queda en el historial (C-12),
    una vez por apertura y no una por cada imagen."""

    def __init__(self, repositorio: RepositorioNavegacionRobot, eventos: RegistroEventos) -> None:
        self._repositorio = repositorio
        self._eventos = eventos

    async def ejecutar(
        self, trabajo_id: int, orden: int, actor: str, usuario_id: int
    ) -> bytes | None:
        captura = await self._repositorio.captura(trabajo_id, orden)
        if captura is not None and orden == 1:
            await self._eventos.registrar(
                Evento(
                    cuenta_medica_id=None,
                    sesion_usuario_id=usuario_id,
                    tipo_evento=TIPO_EVENTO_NAVEGACION_CONSULTADA,
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"trabajo_id": trabajo_id},
                )
            )
        return captura
