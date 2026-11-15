"""Puertos del contexto de codificacion CPMS (Seccion 5.2, 8.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.dominio.cpms.valores import CandidatoCpms, FiltrosSugerencia, ProcedimientoCpms


class ErrorCpms(Exception):
    pass


class ErrorCodigoCpmsInexistente(ErrorCpms):
    """Seccion 8.2: 'un codigo inexistente se rechaza con error'. Sostiene
    el indicador de 100% de coincidencia del R1.3 (Seccion 1.3)."""


class MotorSugerenciaCpms(Protocol):
    """Puerto sobre el motor de recuperacion lexica (Seccion 8.2, puntos
    4-6). No conoce la nocion de 'codigo valido' ni decide sobre
    coincidencia exacta -- eso es un cruce con el catalogo vigente, que
    resuelve el caso de uso via RepositorioCpms. Sincrono a proposito: no
    hace E/S, solo computo en memoria sobre el indice ya construido; quien
    lo llama decide si correrlo en un hilo aparte (ver SugerirCodigoCpms)."""

    def sugerir(
        self, descripcion_normalizada: str, filtros: FiltrosSugerencia, maximo: int
    ) -> tuple[CandidatoCpms, ...]: ...


class RepositorioCpms(Protocol):
    async def version_vigente(self) -> tuple[int, str]:
        """(cpms_version_id, etiqueta) de la version vigente: la mas
        reciente cargada (Seccion 8.2: 'cada ejecucion agrega una version
        nueva', sin marcar ninguna como vigente de forma explicita)."""
        ...

    async def obtener_candidato(self, cpms_version_id: int, codigo: str) -> CandidatoCpms | None:
        """None si el codigo no existe en esa version (Seccion 8.2, punto
        3: coincidencia exacta)."""
        ...

    async def listar_procedimientos(self, cpms_version_id: int) -> list[ProcedimientoCpms]:
        """Todos los procedimientos de una version, para construir el
        indice del motor (Seccion 8.2, punto 7). No lo usan los casos de
        uso de sugerencia/confirmacion, solo el constructor del indice
        (ver infraestructura/cpms/indice.py)."""
        ...

    async def listar_versiones(self) -> list[VersionCpms]:
        """Todas las versiones cargadas, mas reciente primero (Fase 18,
        `GET /catalogo-cpms/versiones`)."""
        ...

    async def confirmar_codigo(self, datos: DatosConfirmacionCodigo) -> int:
        """Persiste procedimiento_facturado (Seccion 8.2: 'codigo
        confirmado, origen, posicion aceptada, usuario, instante y version
        del catalogo'). Devuelve el id creado."""
        ...


@dataclass(frozen=True, slots=True)
class VersionCpms:
    """Fila de `cpms_version` para el listado administrativo (Fase 18):
    no incluye los procedimientos, solo su identidad y procedencia."""

    id: int
    etiqueta: str
    conteo: int
    archivos_origen: list[dict[str, str]]
    creado_en: datetime


@dataclass(frozen=True, slots=True)
class DatosConfirmacionCodigo:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) para
    `confirmar_codigo`: junta lo que trae `ConfirmacionCodigoCpms` (entrada
    del usuario) con lo que el caso de uso deriva (`cpms_version_id`,
    `origen_codigo`, `confirmado_en`), sin exceder el limite de 5
    parametros por funcion (Seccion 3)."""

    cuenta_id: int
    descripcion_registrada: str
    codigo_asignado: str
    cpms_version_id: int
    origen_codigo: str
    posicion_aceptada: int | None
    usuario_confirmo_id: int
    cantidad: int
    monto_unitario: Decimal
    fecha: date
    confirmado_en: datetime
