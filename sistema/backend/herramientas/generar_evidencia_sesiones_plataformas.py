"""Genera reportes/evidencia_sesiones_plataformas.csv (Seccion 13 del
plan v3, nuevo respecto del v2): "solicitudes de sesion, intentos de
CAPTCHA, duracion del ingreso y vencimientos, sin guardar imagenes ni
respuestas".

Por eso esta herramienta nunca lee `sesion_plataforma.imagen_captcha` ni
`sesion_plataforma.respuesta_captcha` -- ninguna de las dos columnas se
proyecta en la consulta, ni siquiera para descartarlas despues (Seccion
13: "prohibido registrar en logs... respuestas de CAPTCHA").

Uso (desde sistema/backend/):
    uv run python herramientas/generar_evidencia_sesiones_plataformas.py
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_plataformas import SesionPlataformaModelo
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "evidencia_sesiones_plataformas.csv"

_ENCABEZADO_COLUMNAS = [
    "sesion_id",
    "plataforma",
    "estado",
    "solicitada_por",
    "creada_en",
    "activa_desde",
    "duracion_ingreso_ms",
    "expira_en",
    "vencida",
    "intentos_captcha",
    "motivo",
]

# Columnas de SesionPlataformaModelo, sin imagen_captcha ni
# respuesta_captcha (Seccion 13).
_COLUMNAS_SIN_DATOS_SENSIBLES = (
    SesionPlataformaModelo.id,
    SesionPlataformaModelo.plataforma,
    SesionPlataformaModelo.estado,
    SesionPlataformaModelo.solicitada_por,
    SesionPlataformaModelo.creada_en,
    SesionPlataformaModelo.activa_desde,
    SesionPlataformaModelo.expira_en,
    SesionPlataformaModelo.intentos,
    SesionPlataformaModelo.motivo,
)


_FilaSesion = sa.Row[
    tuple[int, str, str, str, datetime, "datetime | None", "datetime | None", int, "str | None"]
]


async def _filas() -> list[_FilaSesion]:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(*_COLUMNAS_SIN_DATOS_SENSIBLES).order_by(SesionPlataformaModelo.id)
        )
        return list(resultado.all())


def _duracion_ingreso_ms(creada_en: datetime, activa_desde: datetime | None) -> int | None:
    if activa_desde is None:
        return None
    return int((activa_desde - creada_en).total_seconds() * 1000)


def _vencida(estado: str, expira_en: datetime | None) -> bool:
    if estado == "EXPIRADA":
        return True
    if expira_en is None:
        return False
    return expira_en < datetime.now().astimezone()


def _escribir(ruta: Path, cabecera: list[str], filas: list[_FilaSesion]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        for linea in cabecera:
            archivo.write(f"{linea}\n")
        archivo.write("\n")
        escritor = csv.writer(archivo)
        escritor.writerow(_ENCABEZADO_COLUMNAS)
        for fila in filas:
            (
                sesion_id,
                plataforma,
                estado,
                solicitada_por,
                creada_en,
                activa_desde,
                expira_en,
                intentos,
                motivo,
            ) = fila
            escritor.writerow(
                [
                    sesion_id,
                    plataforma,
                    estado,
                    solicitada_por,
                    creada_en.isoformat(),
                    activa_desde.isoformat() if activa_desde else "",
                    _duracion_ingreso_ms(creada_en, activa_desde),
                    expira_en.isoformat() if expira_en else "",
                    _vencida(estado, expira_en),
                    intentos,
                    motivo or "",
                ]
            )


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    filas = await _filas()
    _escribir(SALIDA, cabecera.como_lineas_comentario_csv(), filas)
    print(f"Reporte generado: {SALIDA} ({len(filas)} sesiones).")


if __name__ == "__main__":
    asyncio.run(main())
