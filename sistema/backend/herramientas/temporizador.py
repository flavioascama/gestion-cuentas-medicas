"""Proceso del temporizador del sistema (CU-05/CU-11, RNF-18): corre en
bucle las tres tareas periodicas que antes se ejecutaban a mano.

- Control de plazos y escalamiento (CU-11): cada
  TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS (60 por defecto).
- Anclaje y verificacion de la cadena de eventos (RNF-18, AD-11, C-10):
  cada TEMPORIZADOR_INTERVALO_CADENA_HORAS (24 por defecto, "diario").

Lo levanta el servicio `temporizador` de docker-compose.yml. Uso manual
(desde sistema/backend/):
    uv run python -m herramientas.temporizador
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.compartido.configuracion import obtener_configuracion
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.repositorio_parametros_sistema_sql import valor_vigente
from app.infraestructura.temporizador import TareaProgramada, ejecutar_pendientes
from herramientas import (
    anclar_cadena_eventos,
    purgar_evidencias,
    reconstruir_proyecciones,
    revisar_comunicaciones_iafas,
    revisar_vencimientos,
    verificar_cadena_eventos,
)

# Cada cuanto el bucle revisa si alguna tarea ya toca. No es el intervalo
# de ninguna tarea: solo la resolucion con la que se detecta que vencio.
_VUELTA_SEGUNDOS = 60


async def _tareas() -> list[TareaProgramada]:
    configuracion = obtener_configuracion()
    minutos = configuracion.temporizador_intervalo_vencimientos_minutos
    horas = configuracion.temporizador_intervalo_cadena_horas
    try:
        async with FabricaSesiones() as sesion:
            minutos = int(
                await valor_vigente(sesion, "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS")
            )
            horas = int(await valor_vigente(sesion, "TEMPORIZADOR_INTERVALO_CADENA_HORAS"))
    except Exception as error:  # noqa: BLE001 - sin base de datos rigen los del despliegue
        print(f"no se pudieron leer los intervalos: {error}", flush=True)
    cada_vencimientos = timedelta(minutes=minutos)
    cada_cadena = timedelta(hours=horas)
    cada_comunicaciones = timedelta(
        minutes=configuracion.temporizador_intervalo_comunicaciones_minutos
    )
    return [
        TareaProgramada("revisar_vencimientos", cada_vencimientos, revisar_vencimientos.main),
        # Portal y correo de la IAFAS: glosas, liquidaciones y pagos.
        TareaProgramada(
            "revisar_comunicaciones_iafas",
            cada_comunicaciones,
            revisar_comunicaciones_iafas.main,
        ),
        TareaProgramada("anclar_cadena_eventos", cada_cadena, anclar_cadena_eventos.main),
        TareaProgramada("verificar_cadena_eventos", cada_cadena, verificar_cadena_eventos.main),
        # C-12: retencion de las evidencias del robot, una vez al dia.
        TareaProgramada("purgar_evidencias", cada_cadena, purgar_evidencias.main),
        # RAS-03: el estado de cada cuenta coincide con el que dicen sus eventos.
        TareaProgramada(
            "verificar_estado_derivado", cada_cadena, reconstruir_proyecciones.verificar
        ),
    ]


async def main() -> None:
    tareas = await _tareas()
    ultimas: dict[str, datetime] = {}
    print("temporizador iniciado: " + ", ".join(t.nombre for t in tareas), flush=True)
    while True:
        ahora = datetime.now(UTC)
        for resultado in await ejecutar_pendientes(tareas, ultimas, ahora):
            estado = "ok" if resultado.exitosa else f"FALLO {resultado.error}"
            print(
                f"[{ahora.isoformat(timespec='seconds')}] {resultado.nombre}: {estado}", flush=True
            )
        await asyncio.sleep(_VUELTA_SEGUNDOS)
        # Los intervalos se vuelven a leer en cada vuelta: un cambio del
        # administrador rige en el siguiente ciclo sin reiniciar el proceso.
        tareas = await _tareas()


if __name__ == "__main__":
    asyncio.run(main())
