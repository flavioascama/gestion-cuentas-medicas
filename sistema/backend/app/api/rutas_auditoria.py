"""CU-07: /cuentas/{id}/auditoria/conformidad. Registrar el resultado de
la auditoria es del analista (Tabla 46, "Registrar el resultado de la
auditoria y las observaciones"); lo consultan los mismos roles que las
observaciones."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.observaciones.conformidad import (
    ConsultarConformidadAuditoria,
    ErrorConformidadYaRegistrada,
    ErrorCuentaInexistenteAuditoria,
    ErrorCuentaSinAuditoriaEnCurso,
    RegistrarConformidadAuditoria,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_conformidad_auditoria_sql import (
    RepositorioConformidadAuditoriaSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

router = APIRouter(prefix="/cuentas/{cuenta_id}/auditoria", tags=["observaciones"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)


class ConformidadAuditoriaRespuesta(BaseModel):
    conforme_en: datetime | None


def construir_registrar_conformidad(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RegistrarConformidadAuditoria:
    return RegistrarConformidadAuditoria(
        RepositorioEstadoCuentaSql(sesion),
        RepositorioConformidadAuditoriaSql(sesion),
        RegistroEventosSql(sesion),
    )


def construir_consultar_conformidad(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> ConsultarConformidadAuditoria:
    return ConsultarConformidadAuditoria(RepositorioConformidadAuditoriaSql(sesion))


@router.get("/conformidad", response_model=ConformidadAuditoriaRespuesta)
async def consultar_conformidad(
    cuenta_id: int,
    caso_uso: ConsultarConformidadAuditoria = Depends(construir_consultar_conformidad),
    _actor: CargaSesion = Depends(_LECTURA),
) -> ConformidadAuditoriaRespuesta:
    return ConformidadAuditoriaRespuesta(conforme_en=await caso_uso.ejecutar(cuenta_id))


@router.post("/conformidad", status_code=status.HTTP_204_NO_CONTENT)
async def registrar_conformidad(
    cuenta_id: int,
    caso_uso: RegistrarConformidadAuditoria = Depends(construir_registrar_conformidad),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> None:
    try:
        await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except ErrorCuentaInexistenteAuditoria as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorCuentaSinAuditoriaEnCurso as error:
        raise ErrorAplicacion(
            "CUENTA_SIN_AUDITORIA_EN_CURSO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorConformidadYaRegistrada as error:
        raise ErrorAplicacion(
            "CONFORMIDAD_YA_REGISTRADA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
