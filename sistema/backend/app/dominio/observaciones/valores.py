"""DTOs del contexto de observaciones/glosas (Seccion 5.2.4.2, Tabla 60;
CU-08 a CU-10)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.dominio.acceso.entidades import NombreRol


class ResultadoObservacion(StrEnum):
    """En que termino la observacion respondida, segun la siguiente
    comunicacion de la aseguradora (2026-11-19)."""

    LEVANTADA = "LEVANTADA"
    MANTENIDA = "MANTENIDA"


class Naturaleza(StrEnum):
    """Tabla 60: las tres naturalezas de observacion que el catalogo de
    motivos clasifica."""

    ADMINISTRATIVA = "ADMINISTRATIVA"
    TECNICA = "TECNICA"
    FINANCIERA = "FINANCIERA"


# Tabla 60: "Responsable asignado" por naturaleza. La tecnica la asigna
# al auditor medico "con el apoyo del analista para la refacturacion",
# pero el responsable PRINCIPAL -- a quien se asigna la observacion y
# quien puede registrar la respuesta (CU-10) -- es uno solo por fila.
ROL_RESPONSABLE_POR_NATURALEZA: dict[Naturaleza, NombreRol] = {
    Naturaleza.ADMINISTRATIVA: NombreRol.ANALISTA,
    Naturaleza.TECNICA: NombreRol.AUDITOR,
    Naturaleza.FINANCIERA: NombreRol.ANALISTA,
}


@dataclass(frozen=True, slots=True)
class MotivoObservacion:
    """Una fila del catalogo parametrizable de motivos (Seccion 5.2.4.2:
    "el sistema mantiene un catalogo de motivos parametrizable, en el
    que cada motivo se asocia a una naturaleza"). A diferencia de CPMS,
    CIE-10 o GTIN, este catalogo no viene de una fuente oficial externa:
    lo define la propia clinica segun los motivos que sus aseguradoras
    comunican en la practica -- por eso no esta versionado como esos
    tres (Seccion 6.1), es una tabla de parametros simple."""

    codigo: str
    descripcion: str
    naturaleza: Naturaleza


@dataclass(frozen=True, slots=True)
class DatosRegistroObservacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) de
    entrada de `RegistrarObservacion.ejecutar` (CU-08)."""

    cuenta_medica_id: int
    motivo_codigo: str
    es_parcial: bool
    detalle_campo_objetado: str | None
    actor: str
    usuario_origen: str | None = None
    # Lo que la aseguradora glosa, si lo comunica (2026-11-19).
    monto_observado: Decimal | None = None


@dataclass(frozen=True, slots=True)
class DatosNuevaObservacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) de
    `RepositorioObservaciones.crear`: los campos ya resueltos por
    `RegistrarObservacion` (motivo validado, naturaleza y responsable ya
    calculados), listos para persistir."""

    cuenta_medica_id: int
    motivo_codigo: str
    naturaleza: Naturaleza
    es_parcial: bool
    detalle_campo_objetado: str | None
    responsable_rol: NombreRol
    registrado_en: datetime
    monto_observado: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Respondedor:
    """Quien registra la respuesta (CU-10)."""

    usuario_id: int
    nombre_usuario: str


@dataclass(frozen=True, slots=True)
class Observacion:
    """Entidad de dominio, tal como la devuelve el repositorio (Seccion
    5.2.4.2 y CU-09)."""

    id: int
    cuenta_medica_id: int
    motivo_codigo: str
    naturaleza: Naturaleza
    es_parcial: bool
    detalle_campo_objetado: str | None
    responsable_rol: NombreRol
    responsable_usuario_id: int | None
    estado: str  # 'ABIERTA' | 'RESPONDIDA'
    respuesta_texto: str | None
    respuesta_sustento: str | None
    registrado_en: datetime
    respondido_en: datetime | None
    # Nombre de la persona asignada, para mostrarlo (2026-11-18).
    responsable_nombres: str | None = None
    # 2026-11-19: cuanto se observo, en que termino y, si vino de la
    # aseguradora, si la respuesta le llego (ver entrega.py).
    monto_observado: Decimal | None = None
    resultado: str | None = None
    resultado_en: datetime | None = None
    entrega_estado: str | None = None
    entrega_en: datetime | None = None
    entrega_solicitada_por: str | None = None
