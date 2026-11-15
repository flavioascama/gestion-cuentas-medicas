"""Generadores de los 8 escenarios de cobertura de ACREDITA SALUD (Seccion
3.3, Seccion 9.1), separados de generar_datos_sinteticos.py para no
superar el limite de 400 lineas por archivo (GUIA_ESTILO_CODIGO.md,
Seccion 3). Un generador por escenario, indexado por nombre (patron
"Estrategia y registro", Seccion 2.2)."""

from __future__ import annotations

import random
from datetime import date
from typing import Any

from faker import Faker

_PREEXISTENCIAS_POSIBLES = [
    "Hipertension arterial",
    "Diabetes mellitus tipo 2",
    "Asma bronquial",
    "Hipotiroidismo",
]


def numero_documento(tipo: str, faker: Faker) -> str:
    if tipo == "1":  # DNI: 8 digitos
        return str(random.randint(10_000_000, 99_999_999))
    if tipo == "2":  # Carnet de extranjeria
        return "CE" + str(random.randint(0, 999999)).zfill(6)
    return "PA" + str(random.randint(0, 999999)).zfill(6)  # Pasaporte


def _escenario_cobertura_vigente(faker: Faker, codigos_ipress_maestro: list[str]) -> dict[str, Any]:
    hoy = date.today()
    return {
        "estado_afiliacion": "ACTIVO",
        "plan": faker.random_element(["PLAN SALUD BASICO", "PLAN SALUD PREFERENTE"]),
        "vigente_desde": hoy.replace(year=hoy.year - 1).isoformat(),
        "vigente_hasta": hoy.replace(year=hoy.year + 1).isoformat(),
    }


def _escenario_cobertura_cancelada(
    faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    hoy = date.today()
    return {
        "estado_afiliacion": "CANCELADO",
        "fecha_cancelacion": hoy.replace(month=1, day=15).isoformat(),
        "motivo": "Termino de vinculo laboral del titular",
    }


def _escenario_preexistencia_declarada(
    faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    return {
        "estado_afiliacion": "ACTIVO",
        "preexistencias_declaradas": [faker.random_element(_PREEXISTENCIAS_POSIBLES)],
    }


def _escenario_diagnostico_en_carencia(
    faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    return {
        "estado_afiliacion": "ACTIVO",
        "diagnostico_en_carencia": {
            "codigo_cie10": None,
            "descripcion": (
                "PENDIENTE: requiere el catalogo CIE-10 (ver docs/PENDIENTES.md, Fase 4)"
            ),
            "dias_restantes_carencia": random.randint(10, 90),
        },
    }


def _escenario_copago_fijo(faker: Faker, codigos_ipress_maestro: list[str]) -> dict[str, Any]:
    return {
        "estado_afiliacion": "ACTIVO",
        "copago": {"tipo": "fijo", "monto": round(random.uniform(20, 80), 2)},
    }


def _escenario_coaseguro_variable(
    faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    return {
        "estado_afiliacion": "ACTIVO",
        "copago": {"tipo": "coaseguro", "porcentaje": random.choice([10, 20, 30])},
    }


def _escenario_atencion_accidental(
    faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    hoy = date.today()
    return {
        "estado_afiliacion": "ACTIVO",
        "atencion_accidental": {
            "declaracion_siniestro": True,
            "fecha_siniestro": hoy.replace(month=3, day=10).isoformat(),
            "descripcion": "Caida accidental en via publica",
        },
    }


def _escenario_paciente_derivado(faker: Faker, codigos_ipress_maestro: list[str]) -> dict[str, Any]:
    return {
        "estado_afiliacion": "ACTIVO",
        "derivacion": {
            "ipress_origen": faker.random_element(codigos_ipress_maestro),
            "motivo": "Referencia por mayor capacidad resolutiva",
        },
    }


_GENERADORES_ESCENARIO = {
    "cobertura_vigente": _escenario_cobertura_vigente,
    "cobertura_cancelada": _escenario_cobertura_cancelada,
    "preexistencia_declarada": _escenario_preexistencia_declarada,
    "diagnostico_en_carencia": _escenario_diagnostico_en_carencia,
    "copago_fijo": _escenario_copago_fijo,
    "coaseguro_variable": _escenario_coaseguro_variable,
    "atencion_accidental": _escenario_atencion_accidental,
    "paciente_derivado": _escenario_paciente_derivado,
}


def datos_escenario(
    escenario: str, faker: Faker, codigos_ipress_maestro: list[str]
) -> dict[str, Any]:
    generador = _GENERADORES_ESCENARIO.get(escenario)
    if generador is None:
        raise ValueError(f"Escenario desconocido: {escenario}")
    return generador(faker, codigos_ipress_maestro)
