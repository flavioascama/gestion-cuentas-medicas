"""Punto unico para obtener el motor de sugerencia listo para usar
(Seccion 8.2, punto 7): 'el indice se construye al iniciar, se persiste en
disco y se reconstruye al cargar una nueva version'."""

from __future__ import annotations

from pathlib import Path

from app.dominio.cpms.puertos import RepositorioCpms
from app.infraestructura.cpms.configuracion_motor import ConfiguracionMotorCpms
from app.infraestructura.cpms.motor_tfidf import MotorSugerenciaCpmsTfidf


async def obtener_motor_vigente(
    repositorio: RepositorioCpms,
    ruta_indice: Path,
    configuracion: ConfiguracionMotorCpms,
) -> MotorSugerenciaCpmsTfidf:
    version_id, etiqueta = await repositorio.version_vigente()

    motor_en_disco = MotorSugerenciaCpmsTfidf.cargar(ruta_indice, configuracion)
    if motor_en_disco is not None and motor_en_disco.cpms_version_id == version_id:
        return motor_en_disco

    procedimientos = await repositorio.listar_procedimientos(version_id)
    motor = MotorSugerenciaCpmsTfidf.construir(procedimientos, version_id, etiqueta, configuracion)
    motor.guardar(ruta_indice)
    return motor
