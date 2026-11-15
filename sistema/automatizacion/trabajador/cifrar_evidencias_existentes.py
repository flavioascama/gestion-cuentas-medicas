"""Cifra la evidencia del robot que se guardo en claro antes del
2026-11-13 (C-12) y actualiza la ruta registrada en `acreditacion`. Es
idempotente: lo ya cifrado no se toca.

Uso (en el contenedor del trabajador, desde /app/automatizacion):
    uv run python -m trabajador.cifrar_evidencias_existentes
"""

from __future__ import annotations

import asyncio

import sqlalchemy as sa
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.modelos_integracion import AcreditacionModelo
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trabajador.configuracion import configuracion
from trabajador.soporte.evidencias import SUFIJO_CIFRADO, AlmacenEvidenciasCifrado


def cifrar_archivos(almacen: AlmacenEvidenciasCifrado) -> int:
    raiz = almacen.raiz / "evidencia_acreditacion"
    planos = [
        archivo
        for archivo in raiz.glob("*/*")
        if archivo.is_file() and not archivo.name.endswith(SUFIJO_CIFRADO)
    ]
    for archivo in planos:
        almacen.cifrar_existente(archivo)
    return len(planos)


async def actualizar_rutas() -> int:
    motor = create_async_engine(configuracion.url_base_datos)
    try:
        async with async_sessionmaker(bind=motor)() as sesion:
            resultado = await sesion.execute(
                sa.update(AcreditacionModelo)
                .where(
                    AcreditacionModelo.ruta_evidencia.is_not(None),
                    AcreditacionModelo.ruta_evidencia.not_like(f"%{SUFIJO_CIFRADO}"),
                )
                .values(ruta_evidencia=AcreditacionModelo.ruta_evidencia + SUFIJO_CIFRADO)
            )
            await sesion.commit()
            return int(getattr(resultado, "rowcount", 0) or 0)
    finally:
        await motor.dispose()


def main() -> None:
    almacen = AlmacenEvidenciasCifrado(
        configuracion.ruta_reportes, configuracion.clave_cifrado_evidencias
    )
    archivos = cifrar_archivos(almacen)
    filas = asyncio.run(actualizar_rutas())
    print(f"Archivos cifrados: {archivos}; rutas actualizadas en acreditacion: {filas}")


if __name__ == "__main__":
    main()
