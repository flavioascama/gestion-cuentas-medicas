"""Navegacion visible del robot (pedido del usuario, 2026-11-17 y 2026-11-18).

El robot trabaja en un navegador sin ventana, dentro del servidor: nadie ve
lo que hace. El administrador puede hacerlo visible, y elige como:

- "ventana": el navegador del robot se abre con su ventana en el equipo
  donde corre el robot. Sirve cuando el robot corre en una computadora con
  pantalla (uso local).
- "sistema": quien pidio la tarea ve el navegador del robot en vivo dentro
  del sistema. Sirve cuando el robot corre en un servidor sin pantalla (uso
  desplegado).

En los dos modos el robot trabaja mas despacio, para que se vea cada accion.
Ninguna imagen queda guardada: el cuadro en vivo es uno solo por trabajo, va
cifrado (C-05, C-12), solo lo ve quien pidio la tarea y se borra al terminar.
Lo que si queda es el registro de pasos (que hizo, donde y cuando), que
consulta el administrador."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

CLAVE_OPCION_NAVEGACION_VISIBLE = "ROBOT_NAVEGACION_VISIBLE"
CLAVE_OPCION_NAVEGACION_MODO = "ROBOT_NAVEGACION_MODO"
MODO_VENTANA = "ventana"
MODO_SISTEMA = "sistema"
MODOS_NAVEGACION = (MODO_VENTANA, MODO_SISTEMA)
TIPO_EVENTO_OPCION_CAMBIADA = "NAVEGACION_ROBOT_OPCION_CAMBIADA"
TIPO_EVENTO_NAVEGACION_CONSULTADA = "NAVEGACION_ROBOT_CONSULTADA"
# El registro de pasos es para revisar lo reciente, no un archivo.
DIAS_RETENCION_PASOS = 7
# Un cuadro mas viejo que esto es de un robot que ya no esta trabajando.
SEGUNDOS_VIGENCIA_CUADRO = 15
# El robot que corre en un equipo con pantalla avisa cada pocos segundos
# que esta encendido; pasado este tiempo sin aviso, se lo da por apagado.
CLAVE_LATIDO_ROBOT_CON_PANTALLA = "ROBOT_CON_PANTALLA_LATIDO"
SEGUNDOS_VIGENCIA_LATIDO = 20


class ErrorModoNavegacion(Exception):
    def __init__(self, modo: str) -> None:
        super().__init__(f"Modo de navegacion desconocido: {modo}.")


@dataclass(frozen=True, slots=True)
class OpcionNavegacion:
    activa: bool
    modo: str


@dataclass(frozen=True, slots=True)
class PasoRegistrado:
    """Lo que el robot anota al terminar un paso."""

    trabajo_id: int
    plataforma: str
    descripcion: str
    url: str


@dataclass(frozen=True, slots=True)
class PasoRobot:
    orden: int
    plataforma: str
    descripcion: str
    url: str
    capturado_en: datetime


@dataclass(frozen=True, slots=True)
class ActividadRobot:
    """Un trabajo del robot con pasos anotados, y quien lo pidio."""

    trabajo_id: int
    tipo: str
    estado: str
    usuario: str
    iniciado_en: datetime
    pasos: int


@dataclass(frozen=True, slots=True)
class CuadroEnVivo:
    """Lo que el navegador del robot muestra en este momento."""

    trabajo_id: int
    url: str
    imagen: bytes
    instante: datetime


@dataclass(frozen=True, slots=True)
class TrabajoEnVivo:
    trabajo_id: int
    tipo: str
    url: str
    actualizado_en: datetime


class RepositorioNavegacionRobot(Protocol):
    async def opcion_navegacion(self) -> OpcionNavegacion: ...

    async def fijar_opcion_navegacion(self, opcion: OpcionNavegacion, actor: str) -> None: ...

    async def registrar_paso(self, paso: PasoRegistrado) -> int:
        """Devuelve el numero de orden del paso dentro de su trabajo."""
        ...

    async def pasos(self, trabajo_id: int) -> list[PasoRobot]: ...

    async def actividad(self, maximo: int) -> list[ActividadRobot]:
        """Trabajos con pasos anotados, el mas reciente primero."""
        ...

    async def guardar_cuadro(self, cuadro: CuadroEnVivo) -> None:
        """Reemplaza el cuadro en vivo del trabajo: nunca hay mas de uno."""
        ...

    async def borrar_cuadros(self) -> None: ...

    async def trabajo_en_vivo(self, usuario: str, desde: datetime) -> TrabajoEnVivo | None:
        """El trabajo que `usuario` pidio y que el robot esta haciendo ahora."""
        ...

    async def imagen_en_vivo(self, trabajo_id: int, usuario: str) -> bytes | None:
        """El cuadro del trabajo, solo si lo pidio `usuario`."""
        ...

    async def purgar_anteriores_a(self, limite: datetime) -> int: ...

    async def registrar_latido_pantalla(self, instante: datetime) -> None:
        """El robot con pantalla avisa que esta encendido."""
        ...

    async def hay_robot_con_pantalla(self, desde: datetime) -> bool: ...


def url_sin_consulta(url: str) -> str:
    """La direccion sin su cadena de consulta: ahi puede viajar el documento
    del asegurado, que no debe quedar en una columna sin cifrar."""
    return url.split("?", 1)[0].split("#", 1)[0]


def limite_de_retencion(reloj: Reloj) -> datetime:
    return reloj.ahora() - timedelta(days=DIAS_RETENCION_PASOS)


def inicio_de_vigencia(reloj: Reloj) -> datetime:
    return reloj.ahora() - timedelta(seconds=SEGUNDOS_VIGENCIA_CUADRO)


def inicio_de_vigencia_latido(reloj: Reloj) -> datetime:
    return reloj.ahora() - timedelta(seconds=SEGUNDOS_VIGENCIA_LATIDO)


def le_toca_atender(
    opcion: OpcionNavegacion, con_pantalla: bool, hay_robot_con_pantalla: bool
) -> bool:
    """A cual de los dos robots le toca la cola. El que corre en un equipo
    con pantalla trabaja solo mientras el administrador pide ver la ventana
    real; el del servidor le cede el turno mientras ese otro este
    encendido, y en cualquier otro caso atiende el."""
    quiere_ventana = opcion.activa and opcion.modo == MODO_VENTANA
    if con_pantalla:
        return quiere_ventana
    return not (quiere_ventana and hay_robot_con_pantalla)


class CambiarNavegacionVisible:
    """Solo el administrador. Queda en el historial quien cambio la opcion."""

    def __init__(self, repositorio: RepositorioNavegacionRobot, eventos: RegistroEventos) -> None:
        self._repositorio = repositorio
        self._eventos = eventos

    async def ejecutar(
        self, opcion: OpcionNavegacion, actor: str, usuario_id: int
    ) -> OpcionNavegacion:
        if opcion.modo not in MODOS_NAVEGACION:
            raise ErrorModoNavegacion(opcion.modo)
        await self._repositorio.fijar_opcion_navegacion(opcion, actor)
        await self._eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento=TIPO_EVENTO_OPCION_CAMBIADA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"activa": opcion.activa, "modo": opcion.modo},
            )
        )
        return opcion


class VerRobotEnVivo:
    """Devuelve el cuadro en vivo de un trabajo a quien lo pidio. Empezar a
    mirar un trabajo queda en el historial (C-12), una vez y no por cuadro."""

    def __init__(self, repositorio: RepositorioNavegacionRobot, eventos: RegistroEventos) -> None:
        self._repositorio = repositorio
        self._eventos = eventos

    async def ejecutar(
        self, trabajo_id: int, actor: str, usuario_id: int, primera: bool
    ) -> bytes | None:
        imagen = await self._repositorio.imagen_en_vivo(trabajo_id, actor)
        if imagen is not None and primera:
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
        return imagen
