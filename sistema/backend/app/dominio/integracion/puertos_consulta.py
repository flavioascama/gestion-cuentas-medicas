"""Puertos de solo lectura del contexto de integracion (Fase 18, Seccion
11): listados y detalle para las pantallas de cuentas y lotes. Separados
de `puertos.py` (que agrupa lectura+escritura por caso de uso, Seccion
7.6/7.8) porque estos no los usa ningun caso de uso de escritura -- son
consultas nuevas, sin contraparte previa a esta fase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Protocol

from app.dominio.integracion.hallazgos import Hallazgo


@dataclass(frozen=True, slots=True)
class ResumenIafas:
    """Fila de `iafas` para poblar el selector de IAFAS de la pantalla de
    generacion de lotes (Fase 19, Seccion 12, pantalla 5): la API de
    lotes exige `iafas_id` (clave interna), que ninguna otra respuesta
    expone junto al codigo visible para el usuario."""

    id: int
    codigo: str
    razon_social: str


class RepositorioIafasConsulta(Protocol):
    async def listar(self) -> list[ResumenIafas]:
        """Todas las IAFAS, ordenadas por codigo."""
        ...


@dataclass(frozen=True, slots=True)
class ResumenCie10:
    """Fila de `cie10_codigo` para el buscador del campo "Diagnostico
    principal (CIE-10)" del formulario de nueva cuenta: el usuario no
    conoce de memoria el codigo, solo la descripcion clinica."""

    codigo: str
    descripcion: str


class RepositorioCie10Consulta(Protocol):
    async def buscar(self, texto: str, limite: int) -> list[ResumenCie10]:
        """Codigos de la version vigente cuyo codigo o descripcion
        contengan `texto` (sin distinguir mayusculas), ordenados por
        codigo. Lista vacia si `texto` esta vacio o no hay ninguna
        version de CIE-10 cargada."""
        ...


@dataclass(frozen=True, slots=True)
class ResumenCuenta:
    id: int
    identificacion_interna: str
    estado: str
    fecha_prestacion: date
    nombres_asegurado: str
    apellidos_asegurado: str
    iafas_codigo: str
    iafas_razon_social: str


@dataclass(frozen=True, slots=True)
class ProcedimientoResumen:
    codigo_asignado: str
    descripcion_registrada: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class ProductoResumen:
    tipo_producto: str
    catalogo: str
    codigo_producto: str
    cantidad_venta: str
    id: int = 0
    correlativo: int = 0
    nombre: str | None = None
    fecha_dispensacion: date | None = None
    monto_presentado: str = "0.00"


@dataclass(frozen=True, slots=True)
class DetalleCuenta:
    id: int
    identificacion_interna: str
    estado: str
    fecha_prestacion: date
    hora_prestacion: time
    numero_historia_clinica: str | None
    diagnostico_principal_cie10: str | None
    nombres_asegurado: str
    apellidos_asegurado: str
    tipo_documento_asegurado: str
    numero_documento_asegurado: str
    iafas_codigo: str
    iafas_razon_social: str
    ipress_codigo: str
    procedimientos: tuple[ProcedimientoResumen, ...]
    productos: tuple[ProductoResumen, ...]
    datos_clinicos_reservados: bool = False


class RepositorioCuentasConsulta(Protocol):
    async def listar(
        self,
        estado: str | None,
        iafas_codigo: str | None = None,
        fecha_prestacion: date | None = None,
        estados: tuple[str, ...] | None = None,
    ) -> list[ResumenCuenta]:
        """Mas reciente primero. `estados` (los de una etapa del ciclo)
        se combina con `estado` si vienen los dos. `estado=None` lista los cuatro estados
        (Seccion 6.3). El filtro por IAFAS/fecha antes solo se aplicaba
        en el frontend, sobre las cuentas ya traidas por `estado`; ahora
        se aplica en la propia consulta SQL."""
        ...

    async def obtener(self, cuenta_medica_id: int) -> DetalleCuenta | None:
        """None si la cuenta no existe."""
        ...


@dataclass(frozen=True, slots=True)
class ResumenLote:
    id: int
    numero: str
    periodo: str
    iafas_codigo: str
    estado: str
    generado_en: datetime
    # Pedido del usuario (revision de UX, 2026-11-11): la bandeja no daba
    # ninguna nocion de volumen o monto por lote. "Monto total" es la
    # suma simple de procedimientos (cantidad * monto_unitario) y
    # productos de farmacia (monto_presentado) de las cuentas del lote --
    # no es el "Monto Presentado"/Base Imponible que exige el Anexo 3 de
    # la trama TEDEF (esa formula vive en mapeo_tedef.yaml y se aplica al
    # generar el lote, no al listarlo); se documenta la diferencia para
    # no sugerir una precision normativa que esta cifra no tiene.
    cantidad_documentos: int
    monto_total: Decimal
    # CU-05: se agoto la ventana de monitoreo sin respuesta de la IAFAS.
    monitoreo_excedido: bool = False


@dataclass(frozen=True, slots=True)
class DetalleLote:
    id: int
    numero: str
    periodo: str
    iafas_codigo: str
    estado: str
    generado_en: datetime
    cantidad_documentos: int
    nombre_s01: str | None
    sha256_s01: str | None
    s01_obtenido_en: datetime | None
    enviado_susalud_en: datetime | None
    version_esquema_tedef: str | None = None
    version_mapeo: str | None = None
    monitoreo_excedido: bool = False


@dataclass(frozen=True, slots=True)
class CuentaDelLote:
    """Fila de la seccion "Cuentas incluidas en el lote" del detalle de
    lote (rediseno pedido por el usuario, 2026-11-11). `monto` usa la
    misma formula no normativa que `ResumenLote.monto_total` (suma de
    procedimientos + productos de farmacia), ahora por cuenta en vez de
    por lote completo."""

    id: int
    identificacion_interna: str
    nombres_asegurado: str
    apellidos_asegurado: str
    monto: Decimal
    # 2026-11-12: el lote es un conjunto de atenciones; cada fila dice
    # tambien en que estado esta cada cuenta y de que fecha es la atencion.
    estado: str = ""
    fecha_prestacion: date | None = None


@dataclass(frozen=True, slots=True)
class InformePrevalidacionLote:
    """Igual que `InformeValidacionLote` (Seccion 7.6), recuperado de la
    base de datos en vez de calculado en el momento (Fase 18)."""

    conforme: bool
    generado_en: datetime
    hallazgos: tuple[Hallazgo, ...]


@dataclass(frozen=True, slots=True)
class ObservacionOficial:
    tabla: str | None
    numero_linea: int | None
    campo_clave: str | None
    campo: str | None
    valor_observado: str | None
    codigo_error: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class ResultadoValidacionOficial:
    etapa: str
    resultado: str
    estado_informado_validador: str | None
    registrado_en: datetime
    observaciones: tuple[ObservacionOficial, ...]


@dataclass(frozen=True, slots=True)
class ResumenAcuse:
    id: int
    resultado_transferencia: str
    motivo_transferencia: str | None
    intentado_en: datetime
    respuesta_receptor: str | None
    motivo_receptor: str | None
    respondido_en: datetime | None


class RepositorioLotesConsulta(Protocol):
    async def listar(
        self,
        periodo: str | None,
        estado: str | None = None,
        iafas_id: int | None = None,
    ) -> list[ResumenLote]:
        """Mas reciente primero. Cada filtro es independiente; con todos
        en None lista todos los lotes."""
        ...

    async def obtener(self, lote_id: int) -> DetalleLote | None:
        """None si el lote no existe."""
        ...

    async def obtener_prevalidacion(self, lote_id: int) -> InformePrevalidacionLote | None:
        """None si el lote no existe o no tiene informe persistido (Fase
        18: solo lo tienen los lotes generados desde esta fase en
        adelante -- ver `modelos_prevalidacion.py`)."""
        ...

    async def obtener_validacion_oficial(self, lote_id: int) -> list[ResultadoValidacionOficial]:
        """Una entrada por etapa registrada (FORMA, DETALLADA), en el
        orden en que `RegistrarResultadoValidador` (Fase 16) las fue
        guardando."""
        ...

    async def obtener_acuses(self, lote_id: int) -> list[ResumenAcuse]:
        """Uno por intento de transmision (Seccion 7.8), mas reciente
        primero."""
        ...

    async def obtener_cuentas(self, lote_id: int) -> list[CuentaDelLote]:
        """Las cuentas medicas incluidas en el lote, con su monto. Lista
        vacia si el lote no existe o no tiene ninguna cuenta (no deberia
        pasar en la practica, un lote siempre se genera con al menos una,
        pero no se asume)."""
        ...

    async def obtener_ruta_s01(self, lote_id: int) -> str | None:
        """Ruta en disco del .S01 ya obtenido del validador TEDEF Web
        (Fase 16), o None si el lote no existe o todavia no tiene uno."""
        ...
