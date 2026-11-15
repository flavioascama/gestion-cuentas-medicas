"""Caso de uso `POST /catalogo-cpms/versiones` (Fase 18, Seccion 11):
vuelve a leer las `Parte_N_...xlsx` de `docs/fuentes/` y agrega una
version nueva al catalogo CPMS, sin modificar las anteriores -- misma
logica que `herramientas/cargar_cpms.py` (Fase 4), reutilizada desde
`lector_catalogo_cpms.py` para no duplicarla. Vive en infraestructura y
no en `app/dominio/cpms/`, igual que `GenerarLote`: lee archivos del
sistema de archivos, sin alternativa intercambiable (Seccion 5.2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.infraestructura.cpms.lector_catalogo_cpms import descubrir_partes, leer_procedimientos
from app.infraestructura.persistencia.modelos_cpms import (
    CpmsProcedimientoModelo,
    CpmsVersionModelo,
)


class ErrorSinArchivosCpms(Exception):
    """No hay ninguna 'Parte_*.xlsx' en docs/fuentes/ (Fase 18: a
    diferencia del script de linea de comandos, la API no puede pedirle
    al usuario que revise la carpeta -- devuelve un error de negocio)."""


@dataclass(frozen=True, slots=True)
class ResultadoCargaCpms:
    version_id: int
    etiqueta: str
    conteo: int


class CargarCatalogoCpms:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def ejecutar(self, etiqueta: str | None) -> ResultadoCargaCpms:
        rutas = descubrir_partes()
        if not rutas:
            raise ErrorSinArchivosCpms("No se hallaron archivos 'Parte_*.xlsx' en docs/fuentes/.")

        todos_los_procedimientos = []
        archivos_origen = []
        for ruta in rutas:
            procedimientos = leer_procedimientos(ruta)
            huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
            archivos_origen.append({"archivo": ruta.name, "huella_sha256": huella})
            todos_los_procedimientos.extend(procedimientos)

        version = CpmsVersionModelo(
            etiqueta=etiqueta or date.today().isoformat(),
            archivos_origen=archivos_origen,
            conteo=len(todos_los_procedimientos),
        )
        self._sesion.add(version)
        await self._sesion.flush()

        self._sesion.add_all(
            CpmsProcedimientoModelo(cpms_version_id=version.id, **datos)
            for datos in todos_los_procedimientos
        )
        await self._sesion.commit()
        return ResultadoCargaCpms(
            version_id=version.id, etiqueta=version.etiqueta, conteo=version.conteo
        )
