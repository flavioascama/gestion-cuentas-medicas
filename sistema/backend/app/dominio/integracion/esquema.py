"""Representacion tipada del esquema TEDEF (Seccion 7.1), independiente de
como se cargo (YAML). La infraestructura construye estos objetos a partir
de configuracion/esquema_tedef/esquema_2025_10.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CampoEsquema:
    numero: int
    nombre: str
    obligatorio: bool
    longitud: int
    decimales: int | None
    posicion_inicial: int


@dataclass(frozen=True, slots=True)
class TablaEsquema:
    id: str
    nombre: str
    prefijo: str
    obligatoria: bool
    condicional: bool
    longitud_registro: int
    campos: tuple[CampoEsquema, ...]

    def campo(self, numero: int) -> CampoEsquema:
        for campo in self.campos:
            if campo.numero == numero:
                return campo
        raise KeyError(f"{self.id} no tiene el campo {numero}")
