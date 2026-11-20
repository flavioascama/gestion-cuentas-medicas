"""La Solicitud de Atencion Medica de la acreditacion vigente, descifrada.
La ven quienes ven la acreditacion (analista, auditor, jefe); tesoreria y
gerencia no ven el acto medico."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.api.dependencias import requiere_rol
from app.api.dependencias_acreditacion import construir_ver_solicitud_atencion
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.acreditacion.solicitud_atencion import (
    ErrorSolicitudAtencionNoDisponible,
    VerSolicitudAtencion,
)

router = APIRouter(prefix="/cuentas/{cuenta_id}/acreditacion", tags=["cuentas"])

ROLES_SOLICITUD_ATENCION = (NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)
_VE_SOLICITUD = requiere_rol(*ROLES_SOLICITUD_ATENCION)


@router.get(
    "/solicitud-atencion",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def ver_solicitud_atencion(
    cuenta_id: int,
    caso_uso: VerSolicitudAtencion = Depends(construir_ver_solicitud_atencion),
    actor: CargaSesion = Depends(_VE_SOLICITUD),
) -> Response:
    try:
        documento = await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except ErrorSolicitudAtencionNoDisponible as error:
        raise ErrorAplicacion(
            "SOLICITUD_ATENCION_NO_DISPONIBLE", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    return Response(
        content=documento.contenido,
        media_type=documento.tipo_contenido,
        headers={"Cache-Control": "no-store"},
    )
