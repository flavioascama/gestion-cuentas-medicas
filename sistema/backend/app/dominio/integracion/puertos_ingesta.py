"""Puertos de ingesta y completitud de la cuenta medica (adenda previa a
R1.4: ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md). Separado de puertos.py y
puertos_consulta.py porque cubre un caso de uso de escritura (ingesta) y
uno de lectura con un efecto secundario acotado (completitud, ver el
docstring de ConsultarCompletitudCuenta en casos_uso_ingesta.py)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Protocol


class ErrorIafasInexistente(Exception):
    def __init__(self, iafas_id: int) -> None:
        super().__init__(f"No existe la IAFAS {iafas_id}.")
        self.iafas_id = iafas_id


@dataclass(frozen=True, slots=True)
class DatosNuevaCuenta:
    """Lo minimo que pide el formulario "Nueva cuenta" (adenda, punto 4):
    datos del paciente, la IAFAS asignada y la fecha de atencion. La
    IPRESS no se pide -- es siempre la unica que opera esta clinica
    (Correccion 3 de esta misma sesion: no tiene sentido pedirle al
    usuario que elija su propia clinica)."""

    tipo_documento_asegurado: str
    numero_documento_asegurado: str
    nombres_asegurado: str
    apellidos_asegurado: str
    iafas_id: int
    fecha_prestacion: date
    hora_prestacion: time
    diagnostico_principal_cie10: str | None


class RepositorioIngestaCuentas(Protocol):
    async def crear_cuenta(self, datos: DatosNuevaCuenta) -> int:
        """Busca el asegurado por (tipo_documento, numero_documento); si no
        existe lo crea (marcado ficticio=True, igual que los datos
        sinteticos: Seccion 6.1). Asigna la unica IPRESS registrada,
        genera identificacion_interna ("CTA-NNNNNN") y numero_historia_clinica
        a partir del id creado. Devuelve el id de la cuenta, en estado
        REGISTRADA. Lanza ErrorIafasInexistente si iafas_id no existe."""
        ...


@dataclass(frozen=True, slots=True)
class PiezaCompletitud:
    """Una fila del panel de completitud (adenda, punto 4): que falta, y
    si tiene una accion concreta para resolverla desde la interfaz."""

    clave: str
    etiqueta: str
    completa: bool
    bloquea: bool
    accion: str | None


@dataclass(frozen=True, slots=True)
class ResultadoCompletitud:
    cuenta_id: int
    estado_cuenta: str
    piezas: tuple[PiezaCompletitud, ...]

    @property
    def completa(self) -> bool:
        return all(p.completa for p in self.piezas if p.bloquea)


@dataclass(frozen=True, slots=True)
class EstadoPiezasCuenta:
    """Lo que el repositorio de completitud necesita leer, ya resuelto
    contra las tablas existentes -- sin inventar columnas nuevas."""

    estado_cuenta: str
    tiene_acreditacion: bool
    cantidad_procedimientos: int
    tiene_comprobante: bool


class RepositorioCompletitudCuenta(Protocol):
    async def obtener_estado_piezas(self, cuenta_id: int) -> EstadoPiezasCuenta | None:
        """None si la cuenta no existe."""
        ...

    async def marcar_facturada(self, cuenta_id: int) -> None:
        """Transicion REGISTRADA -> FACTURADA (Seccion 6.3: la unica que
        hoy la produce de verdad -- ver el docstring de
        ConsultarCompletitudCuenta sobre por que vive aqui)."""
        ...
