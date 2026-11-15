"""Abre la evidencia cifrada de un trabajo de acreditacion (C-12): la
descifra en una carpeta de destino y registra el acceso en el historial de
la cuenta (`EVIDENCIA_DESCIFRADA`, con quien la pidio y que archivos).

Uso (en el contenedor del trabajador, desde /app/automatizacion):
    uv run python -m trabajador.descifrar_evidencia TRABAJO_ID DESTINO --solicitado-por USUARIO
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trabajador.configuracion import configuracion
from trabajador.soporte.evidencias import SUFIJO_CIFRADO, AlmacenEvidenciasCifrado


def descifrar(almacen: AlmacenEvidenciasCifrado, trabajo_id: int, destino: Path) -> list[str]:
    carpeta = Path("evidencia_acreditacion") / str(trabajo_id)
    archivos = sorted((almacen.raiz / carpeta).glob("*" + SUFIJO_CIFRADO))
    if not archivos:
        raise SystemExit(f"No hay evidencia cifrada para el trabajo {trabajo_id}.")
    destino.mkdir(parents=True, exist_ok=True)
    nombres = []
    for archivo in archivos:
        nombre = archivo.name.removesuffix(SUFIJO_CIFRADO)
        (destino / nombre).write_bytes(almacen.leer(str(carpeta / archivo.name)))
        nombres.append(nombre)
    return nombres


async def registrar_acceso(
    cuenta_medica_id: int, trabajo_id: int, archivos: list[str], solicitado_por: str
) -> None:
    motor = create_async_engine(configuracion.url_base_datos)
    try:
        async with async_sessionmaker(bind=motor)() as sesion:
            await RegistroEventosSql(sesion).registrar(
                Evento(
                    cuenta_medica_id=cuenta_medica_id,
                    tipo_evento="EVIDENCIA_DESCIFRADA",
                    actor=solicitado_por,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"trabajo_id": trabajo_id, "archivos": archivos},
                )
            )
    finally:
        await motor.dispose()


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("trabajo_id", type=int)
    argumentos.add_argument("destino", type=Path)
    argumentos.add_argument("--solicitado-por", required=True)
    leidos = argumentos.parse_args()

    almacen = AlmacenEvidenciasCifrado(
        configuracion.ruta_reportes, configuracion.clave_cifrado_evidencias
    )
    archivos = descifrar(almacen, leidos.trabajo_id, leidos.destino)
    traza = json.loads((leidos.destino / "traza.json").read_text(encoding="utf-8"))
    asyncio.run(
        registrar_acceso(
            int(traza["cuenta_medica_id"]), leidos.trabajo_id, archivos, leidos.solicitado_por
        )
    )
    print(f"Evidencia del trabajo {leidos.trabajo_id} descifrada en {leidos.destino}: {archivos}")


if __name__ == "__main__":
    main()
