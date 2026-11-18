"""Navegacion visible del robot (2026-11-17 y 2026-11-18).

El administrador activa la opcion, elige el modo ("ventana" en el equipo del
robot, o "sistema") y consulta el registro de lo que hizo el robot: tarea,
usuario que la pidio, hora y pasos, sin imagenes. El analista y el jefe ven
en vivo el navegador del robot mientras hace la tarea que ellos pidieron; esa
imagen muestra datos del asegurado, por eso el administrador no la ve."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.plataformas import navegacion_robot as dominio
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)

router = APIRouter(prefix="/robot", tags=["robot"])

_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)
_QUIEN_OPERA = requiere_rol(NombreRol.ANALISTA, NombreRol.JEFE)
_CONSULTA_OPCION = requiere_rol(NombreRol.ADMINISTRADOR, NombreRol.ANALISTA, NombreRol.JEFE)
_MAXIMO_ACTIVIDAD = 50


class OpcionNavegacion(BaseModel):
    activa: bool
    modo: Literal["ventana", "sistema"] = "sistema"


class EstadoNavegacion(OpcionNavegacion):
    # Hay un robot encendido en un equipo con pantalla: el unico que puede
    # abrir la ventana real del navegador.
    robot_con_pantalla: bool = False


class PasoRobotRespuesta(BaseModel):
    orden: int
    plataforma: str
    descripcion: str
    url: str
    capturado_en: datetime

    @staticmethod
    def desde_valor(valor: dominio.PasoRobot) -> PasoRobotRespuesta:
        return PasoRobotRespuesta(**campos(valor))


class ActividadRobotRespuesta(BaseModel):
    trabajo_id: int
    tipo: str
    estado: str
    usuario: str
    iniciado_en: datetime
    pasos: int

    @staticmethod
    def desde_valor(valor: dominio.ActividadRobot) -> ActividadRobotRespuesta:
        return ActividadRobotRespuesta(**campos(valor))


class TrabajoEnVivoRespuesta(BaseModel):
    trabajo_id: int
    tipo: str
    url: str
    actualizado_en: datetime


async def _estado_navegacion(sesion: AsyncSession, reloj: Reloj) -> EstadoNavegacion:
    repositorio = RepositorioNavegacionRobotSql(sesion)
    opcion = await repositorio.opcion_navegacion()
    con_pantalla = await repositorio.hay_robot_con_pantalla(
        dominio.inicio_de_vigencia_latido(reloj)
    )
    return EstadoNavegacion(**campos(opcion), robot_con_pantalla=con_pantalla)


@router.get("/navegacion-visible", response_model=EstadoNavegacion)
async def consultar_navegacion_visible(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_CONSULTA_OPCION),
    reloj: Reloj = Depends(obtener_reloj),
) -> EstadoNavegacion:
    return await _estado_navegacion(sesion, reloj)


@router.put("/navegacion-visible", response_model=EstadoNavegacion)
async def cambiar_navegacion_visible(
    solicitud: OpcionNavegacion,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
    reloj: Reloj = Depends(obtener_reloj),
) -> EstadoNavegacion:
    caso_uso = dominio.CambiarNavegacionVisible(
        RepositorioNavegacionRobotSql(sesion), RegistroEventosSql(sesion)
    )
    opcion = dominio.OpcionNavegacion(activa=solicitud.activa, modo=solicitud.modo)
    await caso_uso.ejecutar(opcion, actor.nombre_usuario, actor.usuario_id)
    await sesion.commit()
    return await _estado_navegacion(sesion, reloj)


@router.get("/actividad", response_model=list[ActividadRobotRespuesta])
async def listar_actividad(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[ActividadRobotRespuesta]:
    """Registro del robot, lo mas reciente primero. Solo el administrador
    (pedido del usuario, 2026-11-18)."""
    actividad = await RepositorioNavegacionRobotSql(sesion).actividad(_MAXIMO_ACTIVIDAD)
    return [ActividadRobotRespuesta.desde_valor(a) for a in actividad]


@router.get("/trabajos/{trabajo_id}/pasos", response_model=list[PasoRobotRespuesta])
async def listar_pasos(
    trabajo_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[PasoRobotRespuesta]:
    pasos = await RepositorioNavegacionRobotSql(sesion).pasos(trabajo_id)
    return [PasoRobotRespuesta.desde_valor(p) for p in pasos]


@router.get("/en-vivo", response_model=TrabajoEnVivoRespuesta | None)
async def consultar_en_vivo(
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_QUIEN_OPERA),
    reloj: Reloj = Depends(obtener_reloj),
) -> TrabajoEnVivoRespuesta | None:
    """La tarea que el robot esta haciendo ahora a pedido de quien consulta."""
    trabajo = await RepositorioNavegacionRobotSql(sesion).trabajo_en_vivo(
        actor.nombre_usuario, dominio.inicio_de_vigencia(reloj)
    )
    return TrabajoEnVivoRespuesta(**campos(trabajo)) if trabajo is not None else None


@router.get("/en-vivo/{trabajo_id}/cuadro", response_class=Response)
async def obtener_cuadro_en_vivo(
    trabajo_id: int,
    primera: bool = False,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_QUIEN_OPERA),
) -> Response:
    caso_uso = dominio.VerRobotEnVivo(
        RepositorioNavegacionRobotSql(sesion), RegistroEventosSql(sesion)
    )
    imagen = await caso_uso.ejecutar(trabajo_id, actor.nombre_usuario, actor.usuario_id, primera)
    if imagen is None:
        raise ErrorAplicacion(
            "ROBOT_SIN_CUADRO",
            "El robot no esta trabajando en esa tarea.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    await sesion.commit()
    # La imagen muestra datos del asegurado: no debe quedar en caches.
    return Response(content=imagen, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
