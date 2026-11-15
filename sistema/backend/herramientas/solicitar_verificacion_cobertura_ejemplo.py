"""Registra una cuenta medica en REGISTRADA (sin acreditacion todavia) y
encola su verificacion de cobertura (Seccion 13, entregable de la Fase 11:
"consulta de extremo a extremo con medicion de tiempo").

Las 62 cuentas de herramientas/cargar_cuentas_sinteticas.py (Fase 7) ya
tienen una acreditacion de arranque y estan en FACTURADA -- no sirven para
demostrar el flujo real de esta fase. Este script reutiliza un asegurado,
una IAFAS y la IPRESS ya cargados por ese bootstrap, pero crea una cuenta
medica NUEVA, en REGISTRADA, sin acreditacion, para que
SolicitarVerificacionCobertura tenga algo real que encolar.

Requiere que ya se haya ejecutado herramientas/cargar_cuentas_sinteticas.py
(Fase 7), para tener al menos un asegurado/IAFAS/IPRESS en la base.

Uso (desde sistema/backend/):
    uv run python herramientas/solicitar_verificacion_cobertura_ejemplo.py
"""

from __future__ import annotations

import asyncio
from datetime import date, time

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acreditacion.casos_uso import SolicitarVerificacionCobertura
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_acreditacion_sql import (
    RepositorioAcreditacionSql,
)
from app.infraestructura.reloj import RelojSistema


async def _registrar_cuenta_sin_acreditar(sesion: AsyncSession) -> int:
    asegurado = (
        await sesion.execute(sa.select(AseguradoModelo).order_by(AseguradoModelo.id).limit(1))
    ).scalar_one_or_none()
    ipress = (
        await sesion.execute(sa.select(IpressModelo).order_by(IpressModelo.id).limit(1))
    ).scalar_one_or_none()
    if asegurado is None or ipress is None:
        raise SystemExit(
            "No hay ningun asegurado/IPRESS cargado. Ejecute primero "
            "herramientas/cargar_cuentas_sinteticas.py (Fase 7)."
        )

    resultado = await sesion.execute(sa.select(sa.func.count()).select_from(CuentaMedicaModelo))
    siguiente_indice = resultado.scalar_one() + 1

    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"CTA{siguiente_indice:07d}",
        asegurado_id=asegurado.id,
        iafas_id=asegurado.iafas_id,
        ipress_id=ipress.id,
        fecha_prestacion=date.today(),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica=f"{siguiente_indice:08d}",
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta.id


async def main() -> None:
    async with FabricaSesiones() as sesion:
        cuenta_medica_id = await _registrar_cuenta_sin_acreditar(sesion)
        print(f"cuenta_medica_id registrada: {cuenta_medica_id}")

        caso_uso = SolicitarVerificacionCobertura(
            repositorio=RepositorioAcreditacionSql(sesion),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            reloj=RelojSistema(),
        )
        trabajo_id = await caso_uso.ejecutar(cuenta_medica_id)

    print(f"trabajo_id encolado (CONSULTAR_COBERTURA): {trabajo_id}")
    print(
        "Ahora corra el trabajador (sistema/automatizacion/, docker compose up "
        "trabajador) para que lo procese contra el simulador ACREDITA SALUD."
    )


if __name__ == "__main__":
    asyncio.run(main())
