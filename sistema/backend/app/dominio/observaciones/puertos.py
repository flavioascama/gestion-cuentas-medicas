"""Puertos del contexto de observaciones/glosas (Seccion 5.2.4.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.dominio.acceso.entidades import NombreRol
from app.dominio.observaciones.valores import (
    DatosNuevaObservacion,
    MotivoObservacion,
    Naturaleza,
    Observacion,
    ResultadoObservacion,
)


class RepositorioCatalogoMotivos(Protocol):
    async def obtener(self, codigo: str) -> MotivoObservacion | None:
        """None si el codigo no existe en el catalogo vigente (CU-08)."""
        ...

    async def listar(self) -> list[MotivoObservacion]:
        """CU-08, flujo alternativo: "el analista selecciona el codigo
        del catalogo que le corresponde" -- la pantalla necesita listar
        las opciones."""
        ...


class RepositorioObservaciones(Protocol):
    async def crear(self, datos: DatosNuevaObservacion) -> int:
        """Devuelve el id de la observacion creada, en estado ABIERTA,
        con responsable_usuario_id todavia sin asignar (CU-08: la
        asignacion automatica es por rol; CU-09 puede fijar una persona
        concreta)."""
        ...

    async def obtener(self, observacion_id: int) -> Observacion | None: ...

    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[Observacion]: ...

    async def reasignar(
        self,
        observacion_id: int,
        naturaleza: Naturaleza,
        responsable_rol: NombreRol,
        responsable_usuario_id: int | None,
    ) -> None:
        """CU-09: confirma (mismos valores) o reasigna. Si el jefe
        corrige la naturaleza, quien llama ya recalculo
        `responsable_rol` con `ROL_RESPONSABLE_POR_NATURALEZA` antes de
        invocar este metodo (Seccion 5.2.4.2: "el sistema recalcula el
        responsable propuesto")."""
        ...

    async def responder(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: str | None,
        respondido_en: datetime,
    ) -> None:
        """CU-10: dejar ABIERTA -> RESPONDIDA. No valida aqui que no
        estuviera ya respondida -- lo hace el caso de uso, para poder
        levantar `ErrorObservacionYaRespondida` con todo el contexto de
        dominio antes de tocar la base."""
        ...

    async def fijar_resultado(
        self, cuenta_medica_id: int, resultado: ResultadoObservacion, instante: datetime
    ) -> list[int]:
        """Fija el resultado de las observaciones RESPONDIDAS de la cuenta
        que aun no lo tienen; devuelve sus ids."""
        ...
