"""Comunicaciones de la IAFAS a la clinica (2026-11-13, pedido del usuario):
la conformidad de la auditoria, la observacion (glosa), la liquidacion y el
aviso de pago que la aseguradora envia por su portal o por correo (Tabla 42
de la tesis, actividades 10, 13 y 14 del proceso actual).

El robot las lee de ambos canales y este caso de uso las aplica con los
mismos casos de uso que usaria la persona: CU-07 (conformidad), CU-08
(observacion, con su responsable asignado por naturaleza), CU-12
(liquidacion y conciliacion del pago). Cada comunicacion se aplica una sola
vez (por su codigo), deja un evento en la cuenta con el canal por el que
llego y, si no se puede aplicar (comprobante desconocido, motivo fuera del
catalogo, estado que no la admite), queda registrada como no aplicada y
avisa al analista.

La respuesta a una observacion la sigue elaborando la persona responsable;
al registrarla, el sistema la remite a la IAFAS por su portal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Protocol

from app.dominio.comunicaciones.motivo_no_aplicada import (
    COMPROBANTE_NO_ENCONTRADO,
    RECHAZOS_POR_MONTO,
    motivo_no_aplicada,
)
from app.dominio.comunicaciones.sustento_respuesta import datos_de_respuesta
from app.dominio.liquidacion.casos_uso import ConciliarPago, RegistrarLiquidacion
from app.dominio.liquidacion.errores import ErrorLiquidacionInexistente, ErrorPagoYaConciliado
from app.dominio.observaciones.casos_uso import RegistrarObservacion
from app.dominio.observaciones.conformidad import (
    ErrorConformidadYaRegistrada,
    ErrorCuentaInexistenteAuditoria,
    ErrorCuentaSinAuditoriaEnCurso,
    RegistrarConformidadAuditoria,
)
from app.dominio.observaciones.errores import ErrorMotivoInexistente
from app.dominio.observaciones.valores import DatosRegistroObservacion
from app.dominio.orquestacion.errores import ErrorContinuidadEstados, ErrorTransicionNoDefinida
from app.dominio.pse.documentos import RepositorioDocumentosPago
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj, RepositorioTrabajos

ACTOR_ROBOT_COMUNICACIONES = "robot_comunicaciones_iafas"
# Lo que un caso de uso rechaza por una regla del negocio: la comunicacion
# queda no aplicada y avisa; cualquier otra falla se reintenta.
_RECHAZOS_DE_NEGOCIO: tuple[type[Exception], ...] = (
    ErrorTransicionNoDefinida,
    ErrorContinuidadEstados,
    ErrorMotivoInexistente,
    ErrorCuentaInexistenteAuditoria,
    ErrorCuentaSinAuditoriaEnCurso,
    ErrorConformidadYaRegistrada,
    ErrorLiquidacionInexistente,
    ErrorPagoYaConciliado,
    *RECHAZOS_POR_MONTO,
    ValueError,
)
TIPO_TRABAJO_MONITOREAR_COMUNICACIONES = "MONITOREAR_COMUNICACIONES_IAFAS"
TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS = "ENVIAR_RESPUESTA_IAFAS"


class TipoComunicacion(StrEnum):
    AUDITORIA_CONFORME = "AUDITORIA_CONFORME"
    OBSERVACION = "OBSERVACION"
    LIQUIDACION = "LIQUIDACION"
    PAGO = "PAGO"


class ResultadoComunicacion(StrEnum):
    APLICADA = "APLICADA"
    DUPLICADA = "DUPLICADA"
    NO_APLICADA = "NO_APLICADA"


@dataclass(frozen=True, slots=True)
class ComunicacionIafas:
    codigo: str
    canal: str  # PORTAL | CORREO: por donde la recibio la clinica
    tipo: str
    codigo_iafas: str
    codigo_ipress: str
    documento: str  # serie + numero del comprobante
    datos: dict[str, Any]
    emitida_en: str


@dataclass(frozen=True, slots=True)
class ComunicacionRegistrada:
    codigo: str
    canal: str
    tipo: str
    codigo_iafas: str
    codigo_ipress: str
    documento: str
    datos: dict[str, Any]
    emitida_en: str
    cuenta_medica_id: int | None
    resultado: str
    detalle: str | None
    observacion_id: int | None
    recibida_en: datetime
    respuesta_remitida_en: datetime | None


@dataclass(frozen=True, slots=True)
class Aplicacion:
    """Lo que el repositorio guarda de una comunicacion ya procesada."""

    comunicacion: ComunicacionIafas
    cuenta_medica_id: int | None
    resultado: ResultadoComunicacion
    detalle: str | None
    observacion_id: int | None = None


class RepositorioComunicaciones(Protocol):
    async def ya_registrada(self, codigo: str) -> bool: ...

    async def registrar(self, aplicacion: Aplicacion, recibida_en: datetime) -> None: ...

    async def descartar_cambios_pendientes(self) -> None:
        """Deshace lo que un caso de uso dejo a medias antes de rechazar."""
        ...

    async def codigos_ipress(self) -> list[str]:
        """Las IPRESS de la clinica, cuyas comunicaciones se leen."""
        ...

    async def cuenta_de_documento(self, documento: str) -> int | None:
        """La cuenta del comprobante, vigente o reemplazado."""
        ...

    async def estado_de_cuenta(self, cuenta_id: int) -> str | None:
        """Para decir por que no se aplico una comunicacion."""
        ...

    async def origen_de_observacion(self, observacion_id: int) -> ComunicacionRegistrada | None: ...

    async def marcar_respuesta_remitida(self, codigo: str, instante: datetime) -> None: ...

    async def obtener(self, codigo: str) -> ComunicacionRegistrada | None: ...

    async def revision_pendiente(self) -> int | None:
        """El trabajo de revision que aun no termina, si hay uno."""
        ...

    async def listar(
        self, cuenta_medica_id: int | None = None, limite: int = 200
    ) -> list[ComunicacionRegistrada]: ...


@dataclass(frozen=True, slots=True)
class CasosUsoComunicaciones:
    """Objeto de parametros: los casos de uso con que se aplica cada tipo."""

    conformidad: RegistrarConformidadAuditoria
    observacion: RegistrarObservacion
    liquidacion: RegistrarLiquidacion
    pago: ConciliarPago


def _monto(datos: dict[str, Any], clave: str) -> Decimal:
    try:
        return Decimal(str(datos[clave]))
    except (KeyError, InvalidOperation) as error:
        raise ValueError(f"La comunicacion no trae un {clave} valido.") from error


class ProcesarComunicacionIafas:
    def __init__(
        self,
        repositorio: RepositorioComunicaciones,
        casos: CasosUsoComunicaciones,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._casos = casos
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, comunicacion: ComunicacionIafas) -> ResultadoComunicacion:
        if await self._repositorio.ya_registrada(comunicacion.codigo):
            return ResultadoComunicacion.DUPLICADA
        cuenta_id = await self._repositorio.cuenta_de_documento(comunicacion.documento)
        if cuenta_id is None:
            await self._guardar(
                comunicacion, None, ResultadoComunicacion.NO_APLICADA, COMPROBANTE_NO_ENCONTRADO
            )
            return ResultadoComunicacion.NO_APLICADA
        await self._evento(cuenta_id, "COMUNICACION_IAFAS_RECIBIDA", comunicacion, None)
        try:
            observacion_id = await self._aplicar(cuenta_id, comunicacion)
        except _RECHAZOS_DE_NEGOCIO as error:
            await self._repositorio.descartar_cambios_pendientes()
            detalle = motivo_no_aplicada(error, await self._repositorio.estado_de_cuenta(cuenta_id))
            await self._evento(cuenta_id, "COMUNICACION_IAFAS_NO_APLICADA", comunicacion, detalle)
            await self._guardar(comunicacion, cuenta_id, ResultadoComunicacion.NO_APLICADA, detalle)
            return ResultadoComunicacion.NO_APLICADA
        await self._guardar(
            comunicacion, cuenta_id, ResultadoComunicacion.APLICADA, None, observacion_id
        )
        return ResultadoComunicacion.APLICADA

    async def _aplicar(self, cuenta_id: int, comunicacion: ComunicacionIafas) -> int | None:
        datos, actor = comunicacion.datos, ACTOR_ROBOT_COMUNICACIONES
        if comunicacion.tipo == TipoComunicacion.AUDITORIA_CONFORME:
            await self._casos.conformidad.ejecutar(cuenta_id, actor)
            return None
        if comunicacion.tipo == TipoComunicacion.OBSERVACION:
            resultado = await self._casos.observacion.ejecutar(
                DatosRegistroObservacion(
                    cuenta_medica_id=cuenta_id,
                    motivo_codigo=str(datos.get("motivo_codigo", "")),
                    es_parcial=bool(datos.get("es_parcial", False)),
                    detalle_campo_objetado=str(datos.get("detalle") or "") or None,
                    actor=actor,
                    monto_observado=(
                        _monto(datos, "monto_glosado") if datos.get("monto_glosado") else None
                    ),
                )
            )
            return resultado.observacion_id
        if comunicacion.tipo == TipoComunicacion.LIQUIDACION:
            await self._casos.liquidacion.ejecutar(
                cuenta_id, _monto(datos, "monto_liquidado"), actor
            )
            return None
        if comunicacion.tipo == TipoComunicacion.PAGO:
            await self._casos.pago.ejecutar(cuenta_id, _monto(datos, "monto_pagado"), actor)
            return None
        raise ValueError(f"Tipo de comunicacion desconocido: {comunicacion.tipo}.")

    async def _guardar(
        self,
        comunicacion: ComunicacionIafas,
        cuenta_id: int | None,
        resultado: ResultadoComunicacion,
        detalle: str | None,
        observacion_id: int | None = None,
    ) -> None:
        await self._repositorio.registrar(
            Aplicacion(comunicacion, cuenta_id, resultado, detalle, observacion_id),
            self._reloj.ahora(),
        )

    async def _evento(
        self,
        cuenta_id: int,
        tipo_evento: str,
        comunicacion: ComunicacionIafas,
        detalle: str | None,
    ) -> None:
        datos: dict[str, Any] = {
            "codigo": comunicacion.codigo,
            "canal": comunicacion.canal,
            "tipo": comunicacion.tipo,
            "iafas": comunicacion.codigo_iafas,
        }
        if detalle:
            datos["detalle"] = detalle
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento=tipo_evento,
                actor=ACTOR_ROBOT_COMUNICACIONES,
                estado_previo=None,
                estado_nuevo=None,
                datos=datos,
            )
        )


class EncolarRespuestaIafas:
    """Tras registrar la respuesta a una observacion que llego de la IAFAS,
    encola su remision al portal de la aseguradora. Si la cuenta se
    refacturo (reemplazo o nota), el sustento entregado lleva al final el
    comprobante vigente; lo guardado como respuesta no cambia."""

    def __init__(
        self,
        repositorio: RepositorioComunicaciones,
        trabajos: RepositorioTrabajos,
        reloj: Reloj,
        documentos: RepositorioDocumentosPago | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._trabajos = trabajos
        self._reloj = reloj
        self._documentos = documentos

    async def _refacturacion(
        self, cuenta_medica_id: int | None, sustento: str | None
    ) -> dict[str, str | None]:
        if self._documentos is None or cuenta_medica_id is None:
            return {"sustento": sustento}
        return datos_de_respuesta(await self._documentos.documentos(cuenta_medica_id), sustento)

    async def ejecutar(
        self, observacion_id: int, respuesta: str, sustento: str | None, actor: str
    ) -> int | None:
        origen = await self._repositorio.origen_de_observacion(observacion_id)
        if origen is None:
            return None
        return await self._trabajos.encolar(
            tipo=TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
            carga_util={
                "codigo": origen.codigo,
                "codigo_ipress": origen.codigo_ipress,
                "cuenta_medica_id": origen.cuenta_medica_id,
                "observacion_id": observacion_id,
                "respuesta": respuesta,
                **await self._refacturacion(origen.cuenta_medica_id, sustento),
                "usuario_origen": actor,
            },
            proximo_intento=self._reloj.ahora(),
        )


@dataclass(frozen=True, slots=True)
class RemisionRespuesta:
    codigo: str
    cuenta_medica_id: int
    observacion_id: int
    usuario_origen: str | None


class RegistrarRemisionRespuesta:
    """Deja constancia de que la respuesta ya se entrego en el portal de
    la IAFAS (evento en la cuenta y fecha en la comunicacion)."""

    def __init__(
        self,
        repositorio: RepositorioComunicaciones,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ya_remitida(self, codigo: str) -> bool:
        registrada = await self._repositorio.obtener(codigo)
        return registrada is not None and registrada.respuesta_remitida_en is not None

    async def ejecutar(self, remision: RemisionRespuesta) -> None:
        await self._repositorio.marcar_respuesta_remitida(remision.codigo, self._reloj.ahora())
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=remision.cuenta_medica_id,
                tipo_evento="RESPUESTA_IAFAS_REMITIDA",
                actor=ACTOR_ROBOT_COMUNICACIONES,
                estado_previo=None,
                estado_nuevo=None,
                datos={"codigo": remision.codigo, "observacion_id": remision.observacion_id},
                usuario_origen=remision.usuario_origen,
            )
        )


class ListarComunicacionesIafas:
    def __init__(self, repositorio: RepositorioComunicaciones) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int | None) -> list[ComunicacionRegistrada]:
        return await self._repositorio.listar(cuenta_medica_id)


class SolicitarRevisionComunicaciones:
    """Encola la lectura del portal y del correo de la IAFAS. La pide el
    temporizador o una persona; si ya hay una revision sin terminar, no
    encola otra y devuelve esa."""

    def __init__(
        self, repositorio: RepositorioComunicaciones, trabajos: RepositorioTrabajos, reloj: Reloj
    ) -> None:
        self._repositorio = repositorio
        self._trabajos = trabajos
        self._reloj = reloj

    async def ejecutar(self, solicitado_por: str) -> int:
        pendiente = await self._repositorio.revision_pendiente()
        if pendiente is not None:
            return pendiente
        return await self._trabajos.encolar(
            tipo=TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
            carga_util={"usuario_origen": solicitado_por},
            proximo_intento=self._reloj.ahora(),
        )
