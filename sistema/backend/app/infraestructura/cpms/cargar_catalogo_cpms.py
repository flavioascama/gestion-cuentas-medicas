"""Caso de uso `POST /catalogo-cpms/versiones` (Fase 18, Seccion 11):
lee el Excel con el listado de procedimientos que envia el administrador
y agrega una version nueva al catalogo CPMS, sin modificar las anteriores
-- misma lectura que `herramientas/cargar_cpms.py` (Fase 4), reutilizada
desde `lector_catalogo_cpms.py` para no duplicarla. Vive en infraestructura
y no en `app/dominio/cpms/`, igual que `GenerarLote` (Seccion 5.2)."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO

from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.archivo_catalogo import ErrorArchivoCatalogoInvalido
from app.compartido.fecha_peru import fecha_peru
from app.infraestructura.cpms.lector_catalogo_cpms import leer_procedimientos
from app.infraestructura.persistencia.modelos_cpms import (
    CpmsProcedimientoModelo,
    CpmsVersionModelo,
)


@dataclass(frozen=True, slots=True)
class ResultadoCargaCpms:
    version_id: int
    etiqueta: str
    conteo: int


class CargarCatalogoCpms:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ejecutar(
        self, etiqueta: str | None, nombre_archivo: str, contenido: bytes
    ) -> ResultadoCargaCpms:
        try:
            procedimientos = leer_procedimientos(BytesIO(contenido))
        except (zipfile.BadZipFile, InvalidFileException, KeyError, IndexError, StopIteration) as e:
            raise ErrorArchivoCatalogoInvalido(
                "El archivo no tiene la estructura del listado oficial del MINSA: hoja "
                "'Parte 1', título, encabezado y las 8 columnas de procedimientos."
            ) from e
        if not procedimientos:
            raise ErrorArchivoCatalogoInvalido("El archivo no tiene procedimientos.")

        huella = hashlib.sha256(contenido).hexdigest()
        version = CpmsVersionModelo(
            etiqueta=etiqueta or fecha_peru(datetime.now(UTC)).isoformat(),
            archivos_origen=[{"archivo": nombre_archivo, "huella_sha256": huella}],
            conteo=len(procedimientos),
        )
        self._sesion.add(version)
        await self._sesion.flush()

        self._sesion.add_all(
            CpmsProcedimientoModelo(cpms_version_id=version.id, **datos) for datos in procedimientos
        )
        await self._sesion.commit()
        return ResultadoCargaCpms(
            version_id=version.id, etiqueta=version.etiqueta, conteo=version.conteo
        )
