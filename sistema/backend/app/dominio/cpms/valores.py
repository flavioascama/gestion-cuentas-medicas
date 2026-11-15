"""DTOs del contexto de codificacion CPMS (Seccion 8.2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcedimientoCpms:
    """Un procedimiento del catalogo, tal como lo necesita el motor de
    sugerencia -- sin SQLAlchemy (Seccion 5.2)."""

    codigo: str
    denominacion: str
    codigo_grupo: str
    nombre_grupo: str
    codigo_seccion: str
    nombre_seccion: str
    codigo_subseccion: str
    nombre_subseccion: str


@dataclass(frozen=True, slots=True)
class FiltrosSugerencia:
    codigo_grupo: str | None = None
    codigo_seccion: str | None = None
    codigo_subseccion: str | None = None


@dataclass(frozen=True, slots=True)
class CandidatoCpms:
    codigo: str
    denominacion: str
    codigo_grupo: str
    nombre_grupo: str
    codigo_seccion: str
    nombre_seccion: str
    codigo_subseccion: str
    nombre_subseccion: str
    puntaje: float
    posicion: int


@dataclass(frozen=True, slots=True)
class ResultadoSugerencia:
    cpms_version_id: int
    cpms_version_etiqueta: str
    coincidencia_exacta: bool
    candidatos: tuple[CandidatoCpms, ...]
