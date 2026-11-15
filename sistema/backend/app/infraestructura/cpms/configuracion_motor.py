"""Carga configuracion/cpms/motor_sugerencia.yaml (Seccion 8.2, punto 5:
'pesos en configuracion')."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.compartido.rutas import RAIZ_BACKEND

RUTA_CONFIGURACION_MOTOR = RAIZ_BACKEND / "configuracion" / "cpms" / "motor_sugerencia.yaml"


@dataclass(frozen=True, slots=True)
class ConfiguracionMotorCpms:
    peso_similitud_lexica: float
    peso_similitud_tokens: float
    candidatos_recuperados: int
    candidatos_devueltos: int
    ngramas_caracteres_minimo: int
    ngramas_caracteres_maximo: int
    ngramas_palabras_minimo: int
    ngramas_palabras_maximo: int


@lru_cache
def cargar_configuracion_motor(ruta: Path = RUTA_CONFIGURACION_MOTOR) -> ConfiguracionMotorCpms:
    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo)
    return ConfiguracionMotorCpms(**datos)
