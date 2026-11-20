"""La atencion que llega cerrada desde el sistema hospitalario de la clinica
(2026-11-19): segunda entrada de la cuenta, junto al formulario "Nueva
cuenta". Valores del contrato fijo del sistema hospitalario, sus errores y
los puertos de la fuente y de la importacion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Protocol

from app.dominio.farmacia.dispensacion import DatosProductoDispensado, ProductoCatalogo

TIPO_AMBULATORIA = "AMBULATORIA"
TIPO_EMERGENCIA = "EMERGENCIA"
TIPO_HOSPITALIZACION = "HOSPITALIZACION"
TIPOS_ATENCION = (TIPO_AMBULATORIA, TIPO_EMERGENCIA, TIPO_HOSPITALIZACION)

AREA_PROCEDIMIENTO = "PROCEDIMIENTO"
AREA_LABORATORIO = "LABORATORIO"
AREA_IMAGENES = "IMAGENES"
AREAS_PROCEDIMIENTO = (AREA_PROCEDIMIENTO, AREA_LABORATORIO, AREA_IMAGENES)

VIA_CONSULTA = "consulta"
VIA_ARCHIVO = "archivo"


class ErrorSistemaHospitalarioNoDisponible(Exception):
    """El sistema hospitalario no respondio o respondio con un error."""


class ErrorAtencionNoEncontrada(Exception):
    def __init__(self, atencion_id: str) -> None:
        super().__init__(f"El sistema hospitalario no tiene la atencion {atencion_id}.")
        self.atencion_id = atencion_id


class ErrorAtencionYaImportada(Exception):
    def __init__(self, atencion_id: str, cuenta_id: int) -> None:
        super().__init__(f"La atencion {atencion_id} ya se importo en la cuenta {cuenta_id}.")
        self.atencion_id = atencion_id
        self.cuenta_id = cuenta_id


class ErrorAtencionInvalida(Exception):
    """La atencion no se puede importar; `codigo` dice por que."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass(frozen=True, slots=True)
class PacienteAtencion:
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str


@dataclass(frozen=True, slots=True)
class ProfesionalAtencion:
    """Siempre un medico (contrato del sistema hospitalario)."""

    numero_colegiatura: str
    nombres: str


@dataclass(frozen=True, slots=True)
class HospitalizacionAtencion:
    fecha_ingreso: date | None
    fecha_alta: date | None


@dataclass(frozen=True, slots=True)
class ProcedimientoAtencion:
    """Descripcion sin codigo CPMS: codificar sigue siendo del auditor."""

    descripcion: str
    area: str
    cantidad: int
    monto_unitario: Decimal
    fecha: date


@dataclass(frozen=True, slots=True)
class ProductoAtencion:
    codigo_producto: str
    cantidad: Decimal
    tipo_unidad_dispensacion: str
    monto_unitario: Decimal
    fecha_dispensacion: date


@dataclass(frozen=True, slots=True)
class CopagoAtencion:
    monto: Decimal
    referencia: str
    fecha: date


@dataclass(frozen=True, slots=True)
class AtencionHospitalaria:
    atencion_id: str
    tipo_atencion: str
    fecha_prestacion: date
    hora_prestacion: time
    numero_historia_clinica: str
    paciente: PacienteAtencion
    iafas_codigo: str
    profesional: ProfesionalAtencion
    diagnostico_principal_cie10: str
    diagnosticos_secundarios_cie10: tuple[str, ...]
    hospitalizacion: HospitalizacionAtencion | None
    procedimientos: tuple[ProcedimientoAtencion, ...]
    farmacia: tuple[ProductoAtencion, ...]
    copago_cobrado: CopagoAtencion | None


@dataclass(frozen=True, slots=True)
class ResumenAtencionHospitalaria:
    atencion_id: str
    tipo_atencion: str
    fecha_prestacion: date
    paciente: PacienteAtencion
    iafas_codigo: str


@dataclass(frozen=True, slots=True)
class ProductoImportado:
    """Un producto de la atencion ya validado contra el catalogo GTIN."""

    catalogo: ProductoCatalogo
    datos: DatosProductoDispensado
    monto_presentado: Decimal


@dataclass(frozen=True, slots=True)
class CuentaImportada:
    """Lo que el repositorio guarda, en una sola transaccion, al importar."""

    atencion: AtencionHospitalaria
    iafas_id: int
    productos: tuple[ProductoImportado, ...]
    actor: str


class FuenteAtenciones(Protocol):
    async def listar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        """Lanza ErrorSistemaHospitalarioNoDisponible si no responde."""
        ...

    async def obtener(self, atencion_id: str) -> AtencionHospitalaria | None:
        """None si el sistema hospitalario no tiene esa atencion."""
        ...


class RepositorioImportacionAtencion(Protocol):
    async def cuenta_de_atencion(self, atencion_id: str) -> int | None: ...

    async def atenciones_importadas(self, atencion_ids: list[str]) -> set[str]: ...

    async def iafas_por_codigo(self, codigo: str) -> int | None: ...

    async def cie10_desconocidos(self, codigos: tuple[str, ...]) -> tuple[str, ...]:
        """Los codigos que no estan en la version vigente del catalogo CIE-10."""
        ...

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None: ...

    async def crear_cuenta_importada(self, cuenta: CuentaImportada) -> int:
        """Crea la cuenta REGISTRADA con todo lo de la atencion sin confirmar
        la transaccion: la confirma el registro del evento que sigue."""
        ...
