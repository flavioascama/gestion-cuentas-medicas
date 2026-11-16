"""CU-18: parametros por IAFAS (editables por el administrador; el jefe los
consulta) y parametros del sistema (solo lectura: se fijan en el entorno
del despliegue)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.api.serializacion import campos
from app.compartido.configuracion import obtener_configuracion
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.comunicaciones.correos import ErrorCorreoRemitenteInvalido, validar_remitentes
from app.dominio.plazos.parametros import (
    ActualizarParametrosIafas,
    ActualizarRemitenteIafas,
    ErrorIafasInexistente,
    ErrorParametroInvalido,
    ListarParametrosIafas,
    ParametrosIafas,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_parametros_iafas_sql import (
    RepositorioParametrosIafasSql,
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
    periodicidad_remision_dias: int | None = Field(default=None, ge=1)
    ventana_monitoreo_horas: int | None = Field(default=None, ge=1)
    dias_plazo_respuesta_observacion: int | None = Field(default=None, ge=1)
    dias_plazo_comunicacion_auditoria: int | None = Field(default=None, ge=1)
    dias_plazo_pago_liquidacion: int | None = Field(default=None, ge=1)


class ParametroSistemaRespuesta(BaseModel):
    clave: str
    valor: str


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
    cambios = solicitud.model_dump(exclude_none=True)
    try:
        parametros = await caso_uso.ejecutar(
            iafas_id, cambios, actor.nombre_usuario, actor.usuario_id
        )
    except ErrorIafasInexistente as error:
        raise ErrorAplicacion("IAFAS_NO_ENCONTRADA", str(error), estado_http=404) from error
    except ErrorParametroInvalido as error:
        raise ErrorAplicacion("PARAMETRO_INVALIDO", str(error), estado_http=400) from error
    await sesion.commit()
    return ParametrosIafasRespuesta.desde_valor(parametros)


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
    _actor: CargaSesion = Depends(_SOLO_ADMINISTRADOR),
) -> list[ParametroSistemaRespuesta]:
    configuracion = obtener_configuracion()
    valores = {
        "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO": configuracion.dias_plazo_reenvio_lote_rechazado,
        "DIAS_AVISO_PREVIO_VENCIMIENTO": configuracion.dias_aviso_previo_vencimiento,
        "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA": configuracion.dias_aviso_vigencia_carta_garantia,
        "DURACION_SESION_MINUTOS": configuracion.duracion_sesion_minutos,
        "MAXIMO_INTENTOS_FALLIDOS_SESION": configuracion.maximo_intentos_fallidos_sesion,
        "DURACION_BLOQUEO_SESION_MINUTOS": configuracion.duracion_bloqueo_sesion_minutos,
        "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS": (
            configuracion.temporizador_intervalo_vencimientos_minutos
        ),
        "TEMPORIZADOR_INTERVALO_CADENA_HORAS": configuracion.temporizador_intervalo_cadena_horas,
        "FERIADOS": configuracion.feriados or "—",
    }
    return [ParametroSistemaRespuesta(clave=c, valor=str(v)) for c, v in valores.items()]
