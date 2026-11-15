"""Genera un lote real desde las cuentas cargadas por
cargar_cuentas_sinteticas.py y reporta el resultado (Seccion 13,
entregable de la Fase 7: "un lote conforme generado desde las semillas").

Toma la IAFAS con mas cuentas FACTURADAS disponibles y genera un lote con
todas ellas. Sirve como demostracion reproducible y como script de
verificacion manual tras cualquier cambio al constructor o al validador.

Requiere que ya se hayan ejecutado, en este orden:
    herramientas/cargar_cpms.py
    herramientas/cargar_cuentas_sinteticas.py

Uso (desde sistema/backend/):
    uv run python herramientas/generar_lote_ejemplo.py [--periodo 202609]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import sqlalchemy as sa

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.tedef.generar_lote import GenerarLote


async def _cuentas_facturadas_por_iafas() -> dict[int, list[int]]:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(CuentaMedicaModelo.iafas_id, CuentaMedicaModelo.id)
            .where(CuentaMedicaModelo.estado == "FACTURADA")
            .order_by(CuentaMedicaModelo.iafas_id, CuentaMedicaModelo.id)
        )
        por_iafas: dict[int, list[int]] = {}
        for iafas_id, cuenta_id in resultado.all():
            por_iafas.setdefault(iafas_id, []).append(cuenta_id)
        return por_iafas


async def main(periodo: str) -> None:
    por_iafas = await _cuentas_facturadas_por_iafas()
    if not por_iafas:
        raise SystemExit(
            "No hay cuentas en estado FACTURADA. Ejecute primero "
            "herramientas/cargar_cuentas_sinteticas.py."
        )
    iafas_id, cuenta_ids = max(por_iafas.items(), key=lambda kv: len(kv[1]))
    print(f"IAFAS {iafas_id}: {len(cuenta_ids)} cuentas facturadas disponibles.")

    async with FabricaSesiones() as sesion:
        caso_uso = GenerarLote(
            repositorio=RepositorioLoteFacturacionSql(sesion),
            registro_eventos=RegistroEventosSql(sesion),
            registro_mediciones=RegistroMedicionesSql(sesion),
            reloj=RelojSistema(),
            directorio_salida=raiz_reportes() / "lotes_generados",
        )
        resultado = await caso_uso.ejecutar(
            iafas_id=iafas_id,
            periodo=periodo,
            cuenta_ids=cuenta_ids,
            actor="herramientas/generar_lote_ejemplo.py",
        )

    print(f"conforme: {resultado.conforme}")
    print(f"numero_lote: {resultado.informe.numero_lote}")
    print(f"errores: {len(resultado.informe.errores)}")
    for error in resultado.informe.errores[:20]:
        print(f"  ERROR {error.tabla} {error.campo_numero} {error.campo_nombre} | {error.mensaje}")
    print(f"advertencias: {len(resultado.informe.advertencias)}")

    if resultado.conforme and resultado.rutas_archivos:
        print(f"lote_id: {resultado.lote_id}")
        for ruta in resultado.rutas_archivos:
            print(f"archivo: {ruta} ({Path(ruta).stat().st_size} bytes)")
    else:
        print("No se genero archivo: el lote no es conforme (Seccion 7.6, punto 5).")


if __name__ == "__main__":
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--periodo", default="202609", help="AAAAMM (por defecto: 202609)")
    argumentos = analizador.parse_args()
    asyncio.run(main(argumentos.periodo))
