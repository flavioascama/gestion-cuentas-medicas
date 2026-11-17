"""Navegacion visible del robot (2026-11-17): el administrador activa la
opcion; el analista y el jefe ven las capturas de cada paso. El
administrador no las ve: muestran datos del asegurado, que su rol no
consulta en ninguna otra pantalla."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.plataformas.navegacion_robot import (
    ActividadRobot,
    CambiarNavegacionVisible,
    ObtenerCapturaPaso,
    PasoRobot,
)
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


class PasoRobotRespuesta(BaseModel):
    orden: int
    plataforma: str
    descripcion: str
    url: str
    capturado_en: datetime

    @staticmethod
    def desde_valor(valor: PasoRobot) -> PasoRobotRespuesta:
        return PasoRobotRespuesta(**campos(valor))


class ActividadRobotRespuesta(BaseModel):
    trabajo_id: int
    tipo: str
    estado: str
    iniciado_en: datetime
    pasos: int

    @staticmethod
    def desde_valor(valor: ActividadRobot) -> ActividadRobotRespuesta:
        return ActividadRobotRespuesta(**campos(valor))


@router.get("/navegacion-visible", response_model=OpcionNavegacion)
async def consultar_navegacion_visible(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_CONSULTA_OPCION),
) -> OpcionNavegacion:
    return OpcionNavegacion(activa=await RepositorioNavegacionRobotSql(sesion).navegacion_visible())


@router.put("/navegacion-visible", response_model=OpcionNavegacion)
async def cambiar_navegacion_visible(
    solicitud: OpcionNavegacion,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> OpcionNavegacion:
    caso_uso = CambiarNavegacionVisible(
        RepositorioNavegacionRobotSql(sesion), RegistroEventosSql(sesion)
    )
    activa = await caso_uso.ejecutar(solicitud.activa, actor.nombre_usuario, actor.usuario_id)
    await sesion.commit()
    return OpcionNavegacion(activa=activa)


@router.get("/actividad", response_model=list[ActividadRobotRespuesta])
async def listar_actividad(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_QUIEN_OPERA),
) -> list[ActividadRobotRespuesta]:
    """Trabajos del robot que dejaron capturas, el mas reciente primero."""
    actividad = await RepositorioNavegacionRobotSql(sesion).actividad(_MAXIMO_ACTIVIDAD)
    return [ActividadRobotRespuesta.desde_valor(a) for a in actividad]


@router.get("/trabajos/{trabajo_id}/pasos", response_model=list[PasoRobotRespuesta])
async def listar_pasos(
    trabajo_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_QUIEN_OPERA),
) -> list[PasoRobotRespuesta]:
    pasos = await RepositorioNavegacionRobotSql(sesion).pasos(trabajo_id)
    return [PasoRobotRespuesta.desde_valor(p) for p in pasos]


@router.get("/trabajos/{trabajo_id}/pasos/{orden}/captura", response_class=Response)
async def obtener_captura(
    trabajo_id: int,
    orden: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_QUIEN_OPERA),
) -> Response:
    caso_uso = ObtenerCapturaPaso(RepositorioNavegacionRobotSql(sesion), RegistroEventosSql(sesion))
    captura = await caso_uso.ejecutar(trabajo_id, orden, actor.nombre_usuario, actor.usuario_id)
    if captura is None:
        raise ErrorAplicacion(
            "CAPTURA_NO_ENCONTRADA",
            "No existe esa captura del robot.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    await sesion.commit()
    # La imagen muestra datos del asegurado: no debe quedar en caches.
    return Response(content=captura, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
