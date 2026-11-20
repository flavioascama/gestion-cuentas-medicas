"""Cableado de FastAPI para la Solicitud de Atencion Medica de la
acreditacion vigente (/cuentas/{id}/acreditacion/solicitud-atencion)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends

from app.api.dependencias import obtener_registro_eventos
from app.api.dependencias_cuentas import obtener_repositorio_acreditacion
from app.compartido.configuracion import obtener_configuracion
from app.dominio.acreditacion.puertos import RepositorioAcreditacion
from app.dominio.acreditacion.solicitud_atencion import AlmacenEvidencias, VerSolicitudAtencion
from app.dominio.puertos_comunes import RegistroEventos
from app.infraestructura.seguridad.almacen_evidencias_cifrado import AlmacenEvidenciasCifrado


def obtener_almacen_evidencias() -> AlmacenEvidencias:
    configuracion = obtener_configuracion()
    return AlmacenEvidenciasCifrado(
        Path(configuracion.ruta_reportes), configuracion.clave_cifrado_evidencias
    )


def construir_ver_solicitud_atencion(
    repositorio: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
    almacen: AlmacenEvidencias = Depends(obtener_almacen_evidencias),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> VerSolicitudAtencion:
    return VerSolicitudAtencion(repositorio, almacen, registro_eventos)
