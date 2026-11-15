"""Reconstruye la proyeccion del ciclo de las cuentas desde el almacen de
eventos (AD-04: la proyeccion es derivada; el almacen, la fuente) y
compara el estado que dicen los eventos con el de cada cuenta (RAS-03).

Uso (desde sistema/backend/):
    uv run python -m herramientas.reconstruir_proyecciones
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import sqlalchemy as sa

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo
from app.infraestructura.persistencia.proyeccion_ciclo import (
    ProyeccionCicloCuentaModelo,
    reconstruir_proyecciones,
)


async def comparar_estados(sesion: object) -> list[dict[str, object]]:
    """Cuentas cuyo estado registrado difiere del que derivan sus eventos."""
    filas = await sesion.execute(  # type: ignore[attr-defined]
        sa.select(
            CuentaMedicaModelo.id, CuentaMedicaModelo.estado, ProyeccionCicloCuentaModelo.estado
        )
        .join(
            ProyeccionCicloCuentaModelo,
            ProyeccionCicloCuentaModelo.cuenta_medica_id == CuentaMedicaModelo.id,
        )
        .where(
            ProyeccionCicloCuentaModelo.estado.is_not(None),
            ProyeccionCicloCuentaModelo.estado != CuentaMedicaModelo.estado,
        )
    )
    return [
        {"cuenta_medica_id": cuenta, "estado_registrado": registrado, "estado_eventos": derivado}
        for cuenta, registrado, derivado in filas.all()
    ]


async def main(reconstruir: bool = True) -> None:
    async with FabricaSesiones() as sesion:
        proyectadas = await reconstruir_proyecciones(sesion) if reconstruir else None
        await sesion.commit()
        diferencias = await comparar_estados(sesion)
    reporte = {
        "verificado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "cuentas_proyectadas": proyectadas,
        "estado_coincide": not diferencias,
        "diferencias": diferencias,
    }
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    directorio = raiz_reportes() / "verificaciones_estado_derivado"
    directorio.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (directorio / f"verificacion_{marca}.json").write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8"
    )


async def verificar() -> None:
    """Tarea diaria del temporizador: solo compara, no reconstruye."""
    await main(reconstruir=False)


if __name__ == "__main__":
    asyncio.run(main())
