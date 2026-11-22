"""Control de plazos y escalamiento (CU-11, Seccion 5.2.4.3, Tabla 61,
Fase 27): revisa los cinco hitos controlados y registra un evento por
cada aviso o escalamiento nuevo.

El actor principal de CU-11 es el "temporizador del sistema" (Tabla
51/Anexo C): una corrida periodica sin usuario que la solicite, no un
trabajo de la cola transaccional del trabajador. Por eso, igual que
`verificar_cadena_eventos.py` y `anclar_cadena_eventos.py` (Fase 24), se
expone como una herramienta de linea de comandos de invocacion manual;
la automatizacion de su ejecucion diaria mediante un servicio cron u
ofelia en docker-compose.yml queda pendiente para cuando el prototipo
pase a un entorno operativo (ver docs/PENDIENTES.md, mismo criterio que
la Fase 24).

Uso (desde sistema/backend/):
    uv run python herramientas/revisar_vencimientos.py
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime

from app.compartido.rutas import raiz_reportes
from app.dominio.plazos.casos_uso import RevisarVencimientos
from app.dominio.plazos.parametros_sistema import feriados_desde_texto
from app.dominio.plazos.susalud import RevisarPlazoSusalud
from app.dominio.puertos_comunes import Observabilidad
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_control_susalud_sql import (
    RepositorioControlSusaludSql,
)
from app.infraestructura.persistencia.repositorio_parametros_sistema_sql import valor_vigente
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql
from app.infraestructura.reloj import RelojSistema


async def main() -> None:
    async with FabricaSesiones() as sesion:
        dias_aviso = int(await valor_vigente(sesion, "DIAS_AVISO_PREVIO_VENCIMIENTO"))
        caso_uso = RevisarVencimientos(
            repositorio=RepositorioPlazosSql(
                sesion, int(await valor_vigente(sesion, "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO"))
            ),
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
            dias_aviso_previo_vencimiento=dias_aviso,
            dias_aviso_vigencia_carta_garantia=int(
                await valor_vigente(sesion, "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA")
            ),
        )
        resumen = await caso_uso.ejecutar()
        # RT-05 y RI-16: el envio a SUSALUD en los diez dias habiles.
        resumen_susalud = await RevisarPlazoSusalud(
            repositorio=RepositorioControlSusaludSql(sesion),
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
            feriados=feriados_desde_texto(await valor_vigente(sesion, "FERIADOS")),
            dias_aviso_previo=dias_aviso,
        ).ejecutar()
        await sesion.commit()

    reporte = {
        "revisado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "observaciones": asdict(resumen.observaciones),
        "lotes_rechazados": asdict(resumen.lotes_rechazados),
        "auditorias": asdict(resumen.auditorias),
        "liquidaciones": asdict(resumen.liquidaciones),
        "cartas_garantia": asdict(resumen.cartas_garantia),
        "envio_susalud": asdict(resumen_susalud),
    }
    print(json.dumps(reporte, indent=2, ensure_ascii=False))

    directorio = raiz_reportes() / "revisiones_vencimientos"
    directorio.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ruta = directorio / f"revision_{marca}.json"
    ruta.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreporte de revision de vencimientos escrito en {ruta}")


if __name__ == "__main__":
    asyncio.run(main())
