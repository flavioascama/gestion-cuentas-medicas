"""CU-18: parametros por IAFAS (editables por el administrador; el jefe los
consulta), alta y baja de aseguradoras, y parametros del sistema (el
administrador los cambia; sin cambio, rige el valor del despliegue)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.correos import ErrorCorreoRemitenteInvalido, validar_remitentes
from app.dominio.plazos.parametros import (
    ActualizarParametrosIafas,
    ActualizarRemitenteIafas,
    CrearIafas,
    EliminarIafas,
    ErrorCodigoIafasRepetido,
    ErrorIafasConRegistros,
    ErrorIafasInexistente,
    ErrorParametroInvalido,
    ListarParametrosIafas,
    NuevaIafas,
    ParametrosIafas,
)
from app.dominio.plazos.parametros_sistema import (
    ActualizarParametrosSistema,
    ErrorParametroSistemaInvalido,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_parametros_iafas_sql import (
    RepositorioParametrosIafasSql,
)
from app.infraestructura.persistencia.repositorio_parametros_sistema_sql import (
    RepositorioParametrosSistemaSql,
)

router = APIRouter(prefix="/parametros", tags=["administracion"])

_SOLO_ADMINISTRADOR = requiere_rol(NombreRol.ADMINISTRADOR)
_LECTURA = requiere_rol(NombreRol.ADMINISTRADOR, NombreRol.JEFE)


class ParametrosIafasRespuesta(BaseModel):
    iafas_id: int
    codigo: str
    razon_social: str
    periodicidad_remision_dias: int
    ventana_monitoreo_horas: int
    dias_plazo_respuesta_observacion: int
    dias_plazo_comunicacion_auditoria: int
    dias_plazo_pago_liquidacion: int
    correo_remitente: str | None

    @staticmethod
    def desde_valor(valor: ParametrosIafas) -> ParametrosIafasRespuesta:
        return ParametrosIafasRespuesta(**campos(valor))


class SolicitudParametrosIafas(BaseModel):
    razon_social: str | None = Field(default=None, max_length=200)
    periodicidad_remision_dias: int | None = Field(default=None, ge=1)
    ventana_monitoreo_horas: int | None = Field(default=None, ge=1)
    dias_plazo_respuesta_observacion: int | None = Field(default=None, ge=1)
    dias_plazo_comunicacion_auditoria: int | None = Field(default=None, ge=1)
    dias_plazo_pago_liquidacion: int | None = Field(default=None, ge=1)


class SolicitudNuevaIafas(BaseModel):
    codigo: str
    razon_social: str = Field(max_length=200)
    periodicidad_remision_dias: int = Field(ge=1)
    ventana_monitoreo_horas: int = Field(ge=1)
    dias_plazo_respuesta_observacion: int = Field(ge=1)
    dias_plazo_comunicacion_auditoria: int = Field(ge=1)
    dias_plazo_pago_liquidacion: int = Field(ge=1)


class ParametroSistemaRespuesta(BaseModel):
    clave: str
    valor: str


class SolicitudParametrosSistema(BaseModel):
    valores: dict[str, str]


@router.get("/iafas", response_model=list[ParametrosIafasRespuesta])
async def listar_parametros_iafas(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ParametrosIafasRespuesta]:
    parametros = await ListarParametrosIafas(RepositorioParametrosIafasSql(sesion)).ejecutar()
    return [ParametrosIafasRespuesta.desde_valor(p) for p in parametros]


@router.patch("/iafas/{iafas_id}", response_model=ParametrosIafasRespuesta)
async def actualizar_parametros_iafas(
    iafas_id: int,
    solicitud: SolicitudParametrosIafas,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> ParametrosIafasRespuesta:
    caso_uso = ActualizarParametrosIafas(
        RepositorioParametrosIafasSql(sesion), RegistroEventosSql(sesion)
    )
    cambios = solicitud.model_dump(exclude_none=True, exclude={"razon_social"})
    try:
        parametros = await caso_uso.ejecutar(
            iafas_id, cambios, actor.nombre_usuario, actor.usuario_id, solicitud.razon_social
        )
    except ErrorIafasInexistente as error:
        raise ErrorAplicacion("IAFAS_NO_ENCONTRADA", str(error), estado_http=404) from error
    except ErrorParametroInvalido as error:
        raise ErrorAplicacion("PARAMETRO_INVALIDO", str(error), estado_http=400) from error
    await sesion.commit()
    return ParametrosIafasRespuesta.desde_valor(parametros)


@router.post("/iafas", response_model=ParametrosIafasRespuesta, status_code=status.HTTP_201_CREATED)
async def crear_iafas(
    solicitud: SolicitudNuevaIafas,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> ParametrosIafasRespuesta:
    caso_uso = CrearIafas(RepositorioParametrosIafasSql(sesion), RegistroEventosSql(sesion))
    plazos = solicitud.model_dump(exclude={"codigo", "razon_social"})
    datos = NuevaIafas(codigo=solicitud.codigo, razon_social=solicitud.razon_social, plazos=plazos)
    try:
        creada = await caso_uso.ejecutar(datos, actor.nombre_usuario, actor.usuario_id)
    except ErrorParametroInvalido as error:
        raise ErrorAplicacion("PARAMETRO_INVALIDO", str(error), estado_http=400) from error
    except ErrorCodigoIafasRepetido as error:
        raise ErrorAplicacion("IAFAS_CODIGO_REPETIDO", str(error), estado_http=409) from error
    await sesion.commit()
    return ParametrosIafasRespuesta.desde_valor(creada)


@router.delete("/iafas/{iafas_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_iafas(
    iafas_id: int,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> None:
    caso_uso = EliminarIafas(RepositorioParametrosIafasSql(sesion), RegistroEventosSql(sesion))
    try:
        await caso_uso.ejecutar(iafas_id, actor.nombre_usuario, actor.usuario_id)
    except ErrorIafasInexistente as error:
        raise ErrorAplicacion("IAFAS_NO_ENCONTRADA", str(error), estado_http=404) from error
    except ErrorIafasConRegistros as error:
        raise ErrorAplicacion("IAFAS_CON_REGISTROS", str(error), estado_http=409) from error
    await sesion.commit()


class SolicitudRemitenteIafas(BaseModel):
    correo_remitente: str | None = Field(default=None, max_length=200)


@router.put("/iafas/{iafas_id}/correo-remitente", response_model=ParametrosIafasRespuesta)
async def actualizar_remitente_iafas(
    iafas_id: int,
    solicitud: SolicitudRemitenteIafas,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> ParametrosIafasRespuesta:
    caso_uso = ActualizarRemitenteIafas(
        RepositorioParametrosIafasSql(sesion), RegistroEventosSql(sesion)
    )
    try:
        remitente = validar_remitentes(solicitud.correo_remitente)
        parametros = await caso_uso.ejecutar(
            iafas_id, remitente, actor.nombre_usuario, actor.usuario_id
        )
    except ErrorIafasInexistente as error:
        raise ErrorAplicacion("IAFAS_NO_ENCONTRADA", str(error), estado_http=404) from error
    except ErrorCorreoRemitenteInvalido as error:
        raise ErrorAplicacion("PARAMETRO_INVALIDO", str(error), estado_http=400) from error
    await sesion.commit()
    return ParametrosIafasRespuesta.desde_valor(parametros)


@router.get("/sistema", response_model=list[ParametroSistemaRespuesta])
async def listar_parametros_sistema(
    sesion: AsyncSession = Depends(obtener_sesion),
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[ParametroSistemaRespuesta]:
    valores = await RepositorioParametrosSistemaSql(sesion).vigentes()
    return [ParametroSistemaRespuesta(clave=c, valor=v) for c, v in valores.items()]


@router.patch("/sistema", response_model=list[ParametroSistemaRespuesta])
async def actualizar_parametros_sistema(
    solicitud: SolicitudParametrosSistema,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[ParametroSistemaRespuesta]:
    caso_uso = ActualizarParametrosSistema(
        RepositorioParametrosSistemaSql(sesion), RegistroEventosSql(sesion)
    )
    try:
        valores = await caso_uso.ejecutar(solicitud.valores, actor.nombre_usuario, actor.usuario_id)
    except ErrorParametroSistemaInvalido as error:
        raise ErrorAplicacion("PARAMETRO_INVALIDO", str(error), estado_http=400) from error
    await sesion.commit()
    return [ParametroSistemaRespuesta(clave=c, valor=v) for c, v in valores.items()]
