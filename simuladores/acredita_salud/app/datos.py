"""Carga de datos sinteticos (Seccion 3.3, Seccion 9.1).

Los asegurados vienen de simuladores/datos_semilla/asegurados.json --
generado por herramientas/generar_datos_sinteticos.py del backend (Fase
4), un archivo de DATOS, no de codigo, compartido a proposito entre el
backend y este simulador para que el mismo asegurado cuente la misma
historia en los dos lados (Regla 0.5 prohibe compartir codigo, no un
archivo de datos versionado en simuladores/). Las IAFAS y las cartas de
garantia son datos propios de este simulador, generados deterministamente
a partir de los mismos codigos de IAFAS que ya aparecen en ese archivo, sin
inventar un catalogo de aseguradoras nuevo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Asegurado:
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    iafas_codigo: str
    escenario: str
    estado_afiliacion: str
    datos: dict[str, Any] = field(default_factory=dict)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"


# Nombres sinteticos de IAFAS, deliberadamente genericos (Regla 0.6: nunca
# el nombre de una aseguradora real). Se asignan en orden a los codigos que
# efectivamente aparecen en asegurados.json, no a una lista fija -- si la
# semilla cambia los codigos, la asignacion se recalcula igual.
_NOMBRES_IAFAS_SINTETICOS = (
    "IAFAS Salud Total (ficticia)",
    "IAFAS Bienestar Integral (ficticia)",
    "IAFAS Vida Plena (ficticia)",
    "IAFAS Cuidado Esencial (ficticia)",
    "IAFAS Red Preferente (ficticia)",
    "IAFAS Amparo Medico (ficticia)",
)


class RepositorioDatos:
    def __init__(self, ruta_asegurados: Path) -> None:
        contenido = json.loads(ruta_asegurados.read_text(encoding="utf-8"))
        self._asegurados = tuple(_a_asegurado(fila) for fila in contenido["asegurados"])
        self._metadatos = contenido["metadatos"]
        self._nombres_iafas = self._asignar_nombres_iafas()

    def _asignar_nombres_iafas(self) -> dict[str, str]:
        codigos = sorted({a.iafas_codigo for a in self._asegurados})
        return {
            codigo: _NOMBRES_IAFAS_SINTETICOS[indice % len(_NOMBRES_IAFAS_SINTETICOS)]
            for indice, codigo in enumerate(codigos)
        }

    @property
    def semilla(self) -> int:
        semilla = self._metadatos["semilla"]
        assert isinstance(semilla, int)
        return semilla

    def nombre_iafas(self, codigo: str) -> str:
        return self._nombres_iafas.get(codigo, f"IAFAS {codigo} (ficticia)")

    def codigos_iafas(self) -> list[str]:
        return sorted(self._nombres_iafas)

    def buscar_por_documento(self, tipo: str, numero: str) -> Asegurado | None:
        for asegurado in self._asegurados:
            if asegurado.tipo_documento == tipo and asegurado.numero_documento == numero:
                return asegurado
        return None

    def todos(self) -> tuple[Asegurado, ...]:
        return self._asegurados


def _a_asegurado(fila: dict[str, Any]) -> Asegurado:
    documento = fila["documento"]
    resto = {
        clave: valor
        for clave, valor in fila.items()
        if clave
        not in (
            "documento",
            "nombres",
            "apellidos",
            "iafas_codigo",
            "escenario",
            "ficticio",
            "estado_afiliacion",
        )
    }
    return Asegurado(
        tipo_documento=documento["tipo"],
        numero_documento=documento["numero"],
        nombres=fila["nombres"],
        apellidos=fila["apellidos"],
        iafas_codigo=fila["iafas_codigo"],
        escenario=fila["escenario"],
        estado_afiliacion=fila["estado_afiliacion"],
        datos=resto,
    )
