"""DTOs del control de plazos y escalamiento (Seccion 5.2.4.3, Tabla 61;
CU-11). Cada hito controlado llega del repositorio con su plazo ya
resuelto (parametro de la IAFAS o del sistema, segun corresponda, ya
leido por el adaptador) y con las dos banderas que evitan avisar o
escalar dos veces la misma ocurrencia del hito."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class EstadoHito(StrEnum):
    """Lo que `RevisarVencimientos` concluye sobre un hito abierto, a
    partir de su plazo y de lo que el repositorio ya sabe que se avisa
    o escalo para esta misma ocurrencia."""

    VIGENTE = "VIGENTE"
    PROXIMO_A_VENCER = "PROXIMO_A_VENCER"
    VENCIDO = "VENCIDO"


@dataclass(frozen=True, slots=True)
class ObservacionConPlazo:
    """Hito 1 de la Tabla 61: respuesta a una observacion abierta."""

    observacion_id: int
    cuenta_medica_id: int
    plazo_dias: int
    abierta_desde: datetime
    ya_avisada: bool
    ya_escalada: bool


@dataclass(frozen=True, slots=True)
class CuentaConPlazo:
    """Hitos 2, 3 y 4 de la Tabla 61: todos comparten la misma forma,
    una cuenta en un estado cuyo plazo se cuenta desde el evento que la
    llevo a el (reenvio de un lote rechazado, comunicacion del
    resultado de la auditoria, pago de una liquidacion comunicada)."""

    cuenta_medica_id: int
    plazo_dias: int
    hito_desde: datetime
    ya_avisada: bool
    ya_escalada: bool


@dataclass(frozen=True, slots=True)
class CuentaConVigenciaCartaGarantia:
    """Hito 5 de la Tabla 61: no tiene escalamiento a la jefatura, solo
    aviso al analista responsable (Tabla 3 del Anexo C)."""

    cuenta_medica_id: int
    vigente_hasta: date
    ya_avisada: bool


@dataclass(frozen=True, slots=True)
class ResumenHito:
    """Cuantos hitos de un tipo se revisaron en una corrida de
    `RevisarVencimientos`, y cuantos avisos o escalamientos nuevos
    generaron (nunca re cuenta los que ya estaban avisados/escalados de
    una corrida anterior)."""

    revisados: int = 0
    avisados: int = 0
    escalados: int = 0


@dataclass(frozen=True, slots=True)
class ResumenRevisionPlazos:
    """Lo que devuelve una corrida de `RevisarVencimientos`, uno por
    cada hito de la Tabla 61. `cartas_garantia` nunca tiene escalados:
    ese hito no tiene accion de escalamiento a la jefatura (Tabla 3 del
    Anexo C)."""

    observaciones: ResumenHito
    lotes_rechazados: ResumenHito
    auditorias: ResumenHito
    liquidaciones: ResumenHito
    cartas_garantia: ResumenHito
