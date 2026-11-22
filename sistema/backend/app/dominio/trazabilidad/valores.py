"""DTOs del modulo de trazabilidad con panel de control gerencial
(Seccion 6.2, R3.4; CU-14 a CU-16)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class EventoHistorial:
    """Una fila del historial reconstruido (RT-01/RT-13): "el actor, la
    accion, los estados y la marca temporal" (Tabla 52)."""

    tipo_evento: str
    actor: str
    estado_previo: str | None
    estado_nuevo: str | None
    ocurrido_en: datetime
    datos: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HistorialCuenta:
    """CU-14: el historial reconstruido, mas el resultado de la
    verificacion de integridad de esta cadena en particular (Tabla 52,
    flujo alternativo: "si la verificacion de integridad detecta una
    ruptura... el sistema lo indica en la consulta")."""

    cuenta_medica_id: int
    eventos: list[EventoHistorial]
    cadena_integra: bool
    rupturas: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HistorialLote:
    """RT-13: "reconstruir el historial de cualquier cuenta y de cualquier
    lote" (verificacion de cumplimiento, 2026-11-12: solo existia el de
    la cuenta)."""

    lote_id: int
    eventos: list[EventoHistorial]
    cadena_integra: bool
    rupturas: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DocumentoExpediente:
    """CU-16: un documento asociado que el expediente de auditoria
    incluye junto con los eventos (comprobante de pago, acreditacion)."""

    tipo: str
    referencia: str
    emitido_en: datetime | None
    # El comprobante solo guarda el dia de emision, sin hora.
    fecha_emision: date | None = None


@dataclass(frozen=True, slots=True)
class Expediente:
    cuenta_medica_id: int
    historial: HistorialCuenta
    documentos: list[DocumentoExpediente]
    generado_en: datetime


@dataclass(frozen=True, slots=True)
class FiltroIndicadores:
    """CU-15: "con filtros por IAFAS y periodo" (Tabla 52). `periodo`
    sigue el formato AAAAMM de `lote_facturacion.periodo` (Seccion
    6.1); para las metricas a nivel de cuenta se traduce al rango de
    fechas de ese mes sobre `cuenta_medica.fecha_prestacion`."""

    iafas_codigo: str | None = None
    periodo: str | None = None


@dataclass(frozen=True, slots=True)
class TiempoEtapa:
    """Tiempo promedio que toma llegar a `etapa` desde el estado
    anterior, a partir de la marca temporal de los propios eventos."""

    etapa: str
    promedio_horas: float
    transiciones: int


@dataclass(frozen=True, slots=True)
class DistribucionEstado:
    estado: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class LotesPeriodoEstado:
    """Cantidad de lotes de un periodo en un estado: la serie de la
    evolucion por periodo del panel gerencial (rediseno pedido por el
    usuario, 2026-11-12). Solo respeta el filtro de IAFAS -- con el de
    periodo aplicado quedaria un unico punto; la pantalla resalta el
    periodo elegido en vez de recortar la serie."""

    periodo: str
    estado: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class IndicadoresIafas:
    """Los indicadores de CU-15 desglosados por IAFAS, para comparar
    aseguradoras entre si. Solo respeta el filtro de periodo -- con el
    de IAFAS aplicado quedaria una sola barra; la pantalla resalta la
    IAFAS elegida en vez de ocultar las demas. `monto_registrado` usa la
    misma formula no normativa que `ResumenLote.monto_total`
    (procedimientos + productos de farmacia), no la Base Imponible del
    Anexo 3 de la trama TEDEF."""

    iafas_codigo: str
    iafas_razon_social: str
    cuentas: int
    monto_registrado: Decimal
    cartera_por_cobrar: Decimal
    tasa_glosas: float
    lotes: int
    pct_lotes_observados: float


@dataclass(frozen=True, slots=True)
class CicloCuenta:
    """Una cuenta abierta con su tiempo en el ciclo: desde su primer
    evento (el registro) hasta el instante de la consulta."""

    cuenta_medica_id: int
    identificacion_interna: str
    estado: str
    horas: float


@dataclass(frozen=True, slots=True)
class TiempoCicloCuentas:
    """R3.4 (Tabla 5): "tiempo de ciclo por cuenta". Para las cuentas que
    completaron el ciclo (CERRADA), del registro al cierre; para las
    abiertas, el tiempo que llevan en el ciclo, con las mas antiguas
    primero (donde gerencia tiene que intervenir). Las ANULADA no
    completaron el ciclo de cobro y no entran en ninguno de los dos."""

    cuentas_cerradas: int
    promedio_horas_cerradas: float | None
    mediana_horas_cerradas: float | None
    cuentas_abiertas: int
    promedio_horas_abiertas: float | None
    mas_antiguas_abiertas: list[CicloCuenta]


@dataclass(frozen=True, slots=True)
class RegistrosContingencia:
    """C-18: los resultados registrados en modo de contingencia "quedan
    marcados como registro manual... en el panel de control gerencial"."""

    total: int
    pendientes_revision: int


@dataclass(frozen=True, slots=True)
class IndicadoresCiclo:
    """CU-15: "el tiempo de ciclo por etapa, el porcentaje de lotes
    observados o rechazados, la tasa de glosas, la distribucion de
    cuentas por estado y la cartera por cobrar" (Tabla 52)."""

    tiempo_por_etapa: list[TiempoEtapa]
    pct_lotes_observados: float
    pct_lotes_rechazados: float
    tasa_glosas: float
    distribucion_por_estado: list[DistribucionEstado]
    cartera_por_cobrar: Decimal
    lotes_evaluados: int
    cuentas_evaluadas: int
    lotes_por_periodo: list[LotesPeriodoEstado]
    por_iafas: list[IndicadoresIafas]
    tiempo_ciclo_cuentas: TiempoCicloCuentas
    registros_contingencia: RegistrosContingencia
