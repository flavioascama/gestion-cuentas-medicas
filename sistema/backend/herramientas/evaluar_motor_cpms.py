"""Evalua el motor de sugerencia CPMS sobre el catalogo real completo
(Seccion 13, entregable de la Fase 9: "sugerencias sobre las 12 002 filas
y evidencia de codificacion") y demuestra el ciclo de confirmacion de
extremo a extremo contra Postgres real.

Dos partes:

1. Autorretrieval sobre las 12 002 filas: para cada procedimiento del
   catalogo vigente, se consulta el motor con su propia denominacion
   normalizada y se registra en que posicion (si acaso) el motor devuelve
   su propio codigo. Es una prueba de cobertura, no de robustez: confirma
   que el indice cubre las 12 002 filas sin errores ni omisiones, no que
   el motor tolere errores de tipeo (para eso, ver la parte 2).
2. Un puñado de consultas con ruido deliberado (errores de tipeo, texto
   parcial, sinonimos informales) para demostrar cualitativamente que el
   motor sigue siendo util con la clase de texto libre que en la practica
   escribe un auditor -- y una demostracion completa de ConfirmarCodigoCpms,
   incluido el rechazo de un codigo inexistente (Seccion 8.2).

Uso (desde sistema/backend/):
    uv run python herramientas/evaluar_motor_cpms.py
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.compartido.rutas import RAIZ_BACKEND, raiz_reportes
from app.dominio.cpms.casos_uso import ConfirmacionCodigoCpms, ConfirmarCodigoCpms
from app.dominio.cpms.normalizacion import normalizar
from app.dominio.cpms.puertos import ErrorCodigoCpmsInexistente, RepositorioCpms
from app.dominio.cpms.valores import FiltrosSugerencia
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.cpms.configuracion_motor import cargar_configuracion_motor
from app.infraestructura.cpms.indice import obtener_motor_vigente
from app.infraestructura.cpms.motor_tfidf import MotorSugerenciaCpmsTfidf
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_cpms_sql import RepositorioCpmsSql
from app.infraestructura.reloj import RelojSistema

RUTA_INDICE = RAIZ_BACKEND / ".cache" / "motor_cpms" / "indice.joblib"

_CONSULTAS_CON_RUIDO = [
    "anestesia glandulas salibales",  # typo: "salibales" por "salivales"
    "evaluacion preanestesica paciente hospitalizado",  # sin tildes, orden distinto
    "anestecia oido externo",  # typo: "anestecia"
    "radiologia procedimientos intervencionistas",  # texto parcial
    "terapia electroconvulsiva anestesia",  # orden de palabras invertido
]


async def _autorretrieval(
    motor: MotorSugerenciaCpmsTfidf, repositorio: RepositorioCpms
) -> dict[str, Any]:
    procedimientos = await repositorio.listar_procedimientos(motor.cpms_version_id)
    total = len(procedimientos)
    encontrados_en_posicion_1 = 0
    encontrados_en_top_10 = 0
    no_encontrados: list[str] = []

    inicio = time.monotonic()
    for procedimiento in procedimientos:
        descripcion_normalizada = normalizar(procedimiento.denominacion)
        candidatos = motor.sugerir(descripcion_normalizada, FiltrosSugerencia(), 10)
        posiciones = [c.posicion for c in candidatos if c.codigo == procedimiento.codigo]
        if posiciones:
            encontrados_en_top_10 += 1
            if posiciones[0] == 1:
                encontrados_en_posicion_1 += 1
        else:
            no_encontrados.append(procedimiento.codigo)
    duracion_s = time.monotonic() - inicio

    return {
        "total_procedimientos": total,
        "encontrados_en_posicion_1": encontrados_en_posicion_1,
        "encontrados_en_top_10": encontrados_en_top_10,
        "porcentaje_posicion_1": round(100 * encontrados_en_posicion_1 / total, 2),
        "porcentaje_top_10": round(100 * encontrados_en_top_10 / total, 2),
        "no_encontrados_codigos": no_encontrados[:20],
        "duracion_total_s": round(duracion_s, 2),
        "duracion_promedio_ms": round(1000 * duracion_s / total, 4),
    }


async def _consultas_con_ruido(motor: MotorSugerenciaCpmsTfidf) -> list[dict[str, Any]]:
    resultados = []
    for consulta in _CONSULTAS_CON_RUIDO:
        candidatos = motor.sugerir(normalizar(consulta), FiltrosSugerencia(), 3)
        resultados.append(
            {
                "consulta": consulta,
                "candidatos": [
                    {
                        "codigo": c.codigo,
                        "denominacion": c.denominacion,
                        "puntaje": round(c.puntaje, 4),
                    }
                    for c in candidatos
                ],
            }
        )
    return resultados


async def _confirmar_codigo_valido(
    caso_uso: ConfirmarCodigoCpms, inicio_sugerencia: datetime
) -> int:
    return await caso_uso.ejecutar(
        ConfirmacionCodigoCpms(
            cuenta_medica_id=1,
            descripcion_registrada="Anestesia para procedimientos en glandulas salivales",
            codigo_elegido="00100",
            posicion_aceptada=1,
            usuario_confirmo_id=1,
            cantidad=1,
            monto_unitario=Decimal("50.00"),
            fecha=date.today(),
        ),
        actor="herramientas/evaluar_motor_cpms.py",
        inicio_sugerencia=inicio_sugerencia,
    )


async def _intentar_codigo_inexistente(
    caso_uso: ConfirmarCodigoCpms, inicio_sugerencia: datetime
) -> str | None:
    try:
        await caso_uso.ejecutar(
            ConfirmacionCodigoCpms(
                cuenta_medica_id=1,
                descripcion_registrada="codigo que no existe",
                codigo_elegido="00000-INEXISTENTE",
                posicion_aceptada=None,
                usuario_confirmo_id=1,
                cantidad=1,
                monto_unitario=Decimal("1.00"),
                fecha=date.today(),
            ),
            actor="herramientas/evaluar_motor_cpms.py",
            inicio_sugerencia=inicio_sugerencia,
        )
    except ErrorCodigoCpmsInexistente as error:
        return str(error)
    return None


async def _demostrar_confirmacion(reloj: Reloj) -> dict[str, Any]:
    async with FabricaSesiones() as sesion:
        repositorio = RepositorioCpmsSql(sesion)
        version_id, etiqueta = await repositorio.version_vigente()
        candidato_valido = await repositorio.obtener_candidato(version_id, "00100")
        assert candidato_valido is not None, (
            "El codigo 00100 deberia existir en el catalogo cargado."
        )

        caso_uso = ConfirmarCodigoCpms(
            repositorio=repositorio,
            registro_mediciones=RegistroMedicionesSql(sesion),
            reloj=reloj,
        )
        inicio_sugerencia = reloj.ahora()
        id_confirmado = await _confirmar_codigo_valido(caso_uso, inicio_sugerencia)
        rechazo = await _intentar_codigo_inexistente(caso_uso, inicio_sugerencia)

    return {
        "confirmacion_valida_id": id_confirmado,
        "version_catalogo": etiqueta,
        "rechazo_codigo_inexistente": rechazo,
    }


async def main() -> None:
    configuracion_motor = cargar_configuracion_motor()
    reloj = RelojSistema()

    async with FabricaSesiones() as sesion:
        repositorio = RepositorioCpmsSql(sesion)
        print("construyendo/cargando el indice del motor...")
        motor = await obtener_motor_vigente(repositorio, RUTA_INDICE, configuracion_motor)
        print(f"version vigente: {motor.cpms_version_etiqueta} (id={motor.cpms_version_id})")
        version_catalogo = {"id": motor.cpms_version_id, "etiqueta": motor.cpms_version_etiqueta}

        print("evaluando autorretrieval sobre el catalogo completo...")
        resultado_autorretrieval = await _autorretrieval(motor, repositorio)
        print(json.dumps(resultado_autorretrieval, indent=2, ensure_ascii=False))

        print("\nconsultas con ruido deliberado:")
        resultado_ruido = await _consultas_con_ruido(motor)
        for entrada in resultado_ruido:
            print(f"  '{entrada['consulta']}':")
            for candidato in entrada["candidatos"]:
                denominacion_corta = candidato["denominacion"][:60]
                print(f"    {candidato['codigo']} ({candidato['puntaje']}) {denominacion_corta}")

    print("\ndemostrando ConfirmarCodigoCpms contra Postgres real...")
    resultado_confirmacion = await _demostrar_confirmacion(reloj)
    print(json.dumps(resultado_confirmacion, indent=2, ensure_ascii=False))

    reporte = {
        "version_catalogo": version_catalogo,
        "autorretrieval": resultado_autorretrieval,
        "consultas_con_ruido": resultado_ruido,
        "confirmacion": resultado_confirmacion,
    }
    ruta_reporte = raiz_reportes() / "verificacion_motor_cpms.json"
    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreporte escrito en {ruta_reporte}")


if __name__ == "__main__":
    asyncio.run(main())
