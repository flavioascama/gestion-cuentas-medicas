"""Remite por FTP el ultimo lote VALIDADO y reporta el resultado (Seccion
13, entregable de la Fase 8: "ciclo de envio y acuse completo").

Desde la Fase 13 (Seccion 3 de docs/MIGRACION_V2_A_V3.md) RemitirLote
exige un lote VALIDADO, no GENERADO: el `.S01` ya no lo produce este
backend, lo obtiene el robot del validador TEDEF Web
(RegistrarArchivoTransmision, Fase 16). Hasta que esa fase exista, este
script no tiene forma de dejar un lote en VALIDADO por si solo; se deja
listo para cuando la Fase 16 lo haga posible.

Uso (desde sistema/backend/):
    uv run python herramientas/remitir_lote_ejemplo.py
"""

from __future__ import annotations

import asyncio

import sqlalchemy as sa

from app.compartido.configuracion import obtener_configuracion
from app.dominio.integracion.puertos import ErrorLoteNoRemisible
from app.dominio.puertos_comunes import Observabilidad
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import LoteFacturacionModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_lote_remision_sql import (
    RepositorioLoteRemisionSql,
)
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.tedef.remitir_lote import RemitirLote
from app.infraestructura.transmision.transmisor_ftp import TransmisorFtp


async def _ultimo_lote_validado() -> int | None:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(LoteFacturacionModelo.id)
            .where(LoteFacturacionModelo.estado == "VALIDADO")
            .order_by(LoteFacturacionModelo.id.desc())
            .limit(1)
        )
        fila = resultado.first()
        return fila[0] if fila else None


async def main() -> None:
    lote_id = await _ultimo_lote_validado()
    if lote_id is None:
        raise SystemExit(
            "No hay ningun lote en estado VALIDADO. Ese estado lo produce el "
            "flujo del validador TEDEF Web (Fase 16), todavia no construido."
        )
    print(f"lote_id a remitir: {lote_id}")

    configuracion = obtener_configuracion()
    print(
        f"receptor FTP: {configuracion.ftp_receptor_iafas_host}:"
        f"{configuracion.ftp_receptor_iafas_puerto}"
    )

    async with FabricaSesiones() as sesion:
        caso_uso = RemitirLote(
            repositorio=RepositorioLoteRemisionSql(sesion),
            transmisor=TransmisorFtp(configuracion),
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            reloj=RelojSistema(),
        )
        try:
            resultado = await caso_uso.ejecutar(
                lote_id=lote_id, actor="herramientas/remitir_lote_ejemplo.py"
            )
        except ErrorLoteNoRemisible as error:
            raise SystemExit(f"No se pudo remitir: {error}") from error

    print(f"exitosa: {resultado.exitosa}")
    print(f"acuse_id: {resultado.acuse_id}")
    if not resultado.exitosa:
        print(f"motivo: {resultado.motivo}")
    else:
        print("trabajo MONITOREAR_RESPUESTA_IAFAS encolado (Fase 11).")


if __name__ == "__main__":
    asyncio.run(main())
