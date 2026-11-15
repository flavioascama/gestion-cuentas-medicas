"""Ejecuta un solo ciclo de MonitorearRespuestaIafas sobre el ultimo lote
REMITIDO_IAFAS (Seccion 13, entregable de la Fase 12: "registro automatico
de aceptacion y rechazo").

A diferencia de herramientas/remitir_lote_ejemplo.py, este script no
reemplaza al trabajador: solo corre el mismo caso de uso una vez, de forma
manual, para verificar el ciclo sin esperar al `proximo_intento`
encolado. El trabajador (sistema/automatizacion/) es quien de verdad lo
consume en produccion, vía la cola.

Requiere que ya se haya ejecutado herramientas/remitir_lote_ejemplo.py
(Fase 8) y que el simulador receptor IAFAS (Fase 8) este arriba.

Uso (desde sistema/backend/):
    uv run python herramientas/monitorear_lote_ejemplo.py [--lote-id N]
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta

import sqlalchemy as sa

from app.compartido.configuracion import obtener_configuracion
from app.dominio.integracion.casos_uso import MonitorearRespuestaIafas
from app.dominio.integracion.puertos import ErrorLoteNoMonitoreable
from app.dominio.puertos_comunes import Observabilidad
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import LoteFacturacionModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_monitoreo_respuesta_sql import (
    RepositorioMonitoreoRespuestaSql,
)
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.transmision.consultor_respuesta_receptor_http import (
    ConsultorRespuestaReceptorHttp,
)

_INTERVALO_RECONSULTA_DEMOSTRACION = timedelta(minutes=15)


async def _ultimo_lote_remitido() -> int | None:
    async with FabricaSesiones() as sesion:
        resultado = await sesion.execute(
            sa.select(LoteFacturacionModelo.id)
            .where(LoteFacturacionModelo.estado == "REMITIDO_IAFAS")
            .order_by(LoteFacturacionModelo.id.desc())
            .limit(1)
        )
        fila = resultado.first()
        return fila[0] if fila else None


async def main(lote_id: int | None) -> None:
    if lote_id is None:
        lote_id = await _ultimo_lote_remitido()
    if lote_id is None:
        raise SystemExit(
            "No hay ningun lote en estado REMITIDO_IAFAS. Ejecute primero "
            "herramientas/remitir_lote_ejemplo.py."
        )
    print(f"lote_id a monitorear: {lote_id}")

    configuracion = obtener_configuracion()
    print(f"portal del receptor: {configuracion.receptor_iafas_url_base}")

    async with FabricaSesiones() as sesion:
        caso_uso = MonitorearRespuestaIafas(
            repositorio=RepositorioMonitoreoRespuestaSql(sesion),
            consultor=ConsultorRespuestaReceptorHttp(configuracion.receptor_iafas_url_base),
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
            intervalo_reconsulta=_INTERVALO_RECONSULTA_DEMOSTRACION,
        )
        try:
            resultado = await caso_uso.ejecutar(
                lote_id=lote_id,
                trabajo_creado_en=RelojSistema().ahora(),
                actor="herramientas/monitorear_lote_ejemplo.py",
            )
        except ErrorLoteNoMonitoreable as error:
            raise SystemExit(f"No se pudo monitorear: {error}") from error

    print(f"resultado: {resultado.resultado}")
    if resultado.proximo_intento:
        print(f"proximo_intento: {resultado.proximo_intento.isoformat()}")


if __name__ == "__main__":
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument(
        "--lote-id", type=int, default=None, help="por defecto, el ultimo REMITIDO_IAFAS"
    )
    argumentos = analizador.parse_args()
    asyncio.run(main(argumentos.lote_id))
