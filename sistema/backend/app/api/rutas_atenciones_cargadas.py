"""Carga de atenciones del sistema hospitalario con un archivo Excel, para
el administrador (2026-11-22): `POST /administracion/atenciones-hospitalarias`
y `GET /administracion/atenciones-hospitalarias/plantilla`. Las atenciones
cargadas aparecen en "Importar atencion" del analista."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.compartido.archivo_catalogo import ErrorArchivoCatalogoInvalido, decodificar_xlsx
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.integracion.atencion_hospitalaria import ErrorAtencionInvalida
from app.dominio.integracion.casos_uso_importacion import validar_atencion
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_importacion_atencion_sql import (
    RepositorioImportacionAtencionSql,
)
from app.infraestructura.sistema_hospitalario.esquema_atencion import AtencionJson
from app.infraestructura.sistema_hospitalario.fuente_atenciones_cargadas import (
    codigos_ya_cargados,
    guardar_atenciones,
)
from app.infraestructura.sistema_hospitalario.lector_excel_atenciones import (
    leer_atenciones_xlsx,
    plantilla_xlsx,
)

router = APIRouter(prefix="/administracion/atenciones-hospitalarias", tags=["administracion"])
_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)
_TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class SolicitudCargarAtenciones(BaseModel):
    nombre_archivo: str
    contenido_base64: str


class AtencionesCargadasRespuesta(BaseModel):
    cargadas: int


def _invalido(mensaje: str) -> ErrorAplicacion:
    return ErrorAplicacion(
        "ARCHIVO_ATENCIONES_INVALIDO", mensaje, estado_http=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


async def _exigir_nuevas(sesion: AsyncSession, atenciones: list[AtencionJson]) -> None:
    """Ninguna atencion del archivo puede estar ya cargada ni importada."""
    codigos = [a.atencion_id.strip() for a in atenciones]
    repetidas = await codigos_ya_cargados(sesion, codigos)
    repetidas |= await RepositorioImportacionAtencionSql(sesion).atenciones_importadas(codigos)
    if repetidas:
        raise _invalido(f"Ya existe la atención {', '.join(sorted(repetidas))}.")


@router.post("", response_model=AtencionesCargadasRespuesta, status_code=status.HTTP_201_CREATED)
async def cargar_atenciones(
    solicitud: SolicitudCargarAtenciones,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> AtencionesCargadasRespuesta:
    try:
        contenido = decodificar_xlsx(solicitud.nombre_archivo, solicitud.contenido_base64)
        atenciones = leer_atenciones_xlsx(contenido)
        for atencion in atenciones:
            validar_atencion(atencion.a_valor())
    except ErrorArchivoCatalogoInvalido as error:
        raise _invalido(str(error)) from error
    except ErrorAtencionInvalida as error:
        raise _invalido(str(error)) from error
    await _exigir_nuevas(sesion, atenciones)
    await guardar_atenciones(sesion, atenciones, actor.nombre_usuario)
    return AtencionesCargadasRespuesta(cargadas=len(atenciones))


@router.get("/plantilla")
async def descargar_plantilla(
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> Response:
    return Response(
        content=plantilla_xlsx(),
        media_type=_TIPO_XLSX,
        headers={"Content-Disposition": 'attachment; filename="plantilla_atenciones.xlsx"'},
    )
