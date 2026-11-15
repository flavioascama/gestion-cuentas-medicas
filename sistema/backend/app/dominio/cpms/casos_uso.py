"""Casos de uso del contexto de codificacion CPMS (Seccion 8.2)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.dominio.cpms.normalizacion import es_codigo_candidato, normalizar
from app.dominio.cpms.puertos import (
    DatosConfirmacionCodigo,
    ErrorCodigoCpmsInexistente,
    MotorSugerenciaCpms,
    RepositorioCpms,
    VersionCpms,
)
from app.dominio.cpms.valores import FiltrosSugerencia, ResultadoSugerencia
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import MedicionPaso, RegistroMediciones, Reloj

_MAXIMO_CANDIDATOS_DEVUELTOS = 10


ESTADOS_CODIFICABLES = frozenset({"REGISTRADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"})


class ErrorCuentaNoCodificable(Exception):
    pass


class SugerirCodigoCpms:
    """Seccion 8.2, puntos 1-7. Mide 'la duracion del sistema hasta
    presentar el resultado' (Seccion 6.4); la duracion total hasta la
    confirmacion humana la mide ConfirmarCodigoCpms."""

    def __init__(
        self,
        motor: MotorSugerenciaCpms,
        repositorio: RepositorioCpms,
        registro_mediciones: RegistroMediciones,
        reloj: Reloj,
    ) -> None:
        self._motor = motor
        self._repositorio = repositorio
        self._registro_mediciones = registro_mediciones
        self._reloj = reloj

    async def ejecutar(
        self, descripcion: str, filtros: FiltrosSugerencia, actor: str, cuenta_medica_id: int | None
    ) -> ResultadoSugerencia:
        inicio = self._reloj.ahora()
        version_id, etiqueta = await self._repositorio.version_vigente()
        descripcion_normalizada = normalizar(descripcion)

        if es_codigo_candidato(descripcion_normalizada):
            candidato = await self._repositorio.obtener_candidato(
                version_id, descripcion_normalizada
            )
            if candidato is not None:
                resultado = ResultadoSugerencia(
                    cpms_version_id=version_id,
                    cpms_version_etiqueta=etiqueta,
                    coincidencia_exacta=True,
                    candidatos=(candidato,),
                )
                await self._medir(inicio, cuenta_medica_id, actor, resultado)
                return resultado

        # El motor no hace E/S; se corre en un hilo aparte para no bloquear
        # el bucle de eventos con el computo de similitud (Seccion 5.2: el
        # dominio no sabe que es un hilo de asyncio, solo espera un
        # awaitable -- esto vive aqui, no en el puerto, porque es un
        # detalle de como orquesta el caso de uso, no del contrato).
        candidatos = await asyncio.to_thread(
            self._motor.sugerir, descripcion_normalizada, filtros, _MAXIMO_CANDIDATOS_DEVUELTOS
        )
        resultado = ResultadoSugerencia(
            cpms_version_id=version_id,
            cpms_version_etiqueta=etiqueta,
            coincidencia_exacta=False,
            candidatos=candidatos,
        )
        await self._medir(inicio, cuenta_medica_id, actor, resultado)
        return resultado

    async def _medir(
        self,
        inicio: datetime,
        cuenta_medica_id: int | None,
        actor: str,
        resultado: ResultadoSugerencia,
    ) -> None:
        fin = self._reloj.ahora()
        await self._registro_mediciones.registrar(
            MedicionPaso(
                paso="codificacion_sistema",
                inicio=inicio,
                fin=fin,
                actor=actor,
                cuenta_medica_id=cuenta_medica_id,
                resultado="coincidencia_exacta" if resultado.coincidencia_exacta else "sugerido",
                datos={
                    "cpms_version_id": resultado.cpms_version_id,
                    "candidatos": len(resultado.candidatos),
                },
            )
        )


@dataclass(frozen=True, slots=True)
class ConfirmacionCodigoCpms:
    cuenta_medica_id: int
    descripcion_registrada: str
    codigo_elegido: str
    posicion_aceptada: int | None
    usuario_confirmo_id: int
    cantidad: int
    monto_unitario: Decimal
    fecha: date


class ConfirmarCodigoCpms:
    """Seccion 8.2: 'ningun codigo se incorpora sin confirmacion del
    auditor medico'; 'solo se aceptan codigos existentes en la version
    vigente'."""

    def __init__(
        self,
        repositorio: RepositorioCpms,
        registro_mediciones: RegistroMediciones,
        reloj: Reloj,
        estado_cuenta: RepositorioEstadoCuenta | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._registro_mediciones = registro_mediciones
        self._reloj = reloj
        self._estado_cuenta = estado_cuenta

    async def ejecutar(
        self, confirmacion: ConfirmacionCodigoCpms, actor: str, inicio_sugerencia: datetime
    ) -> int:
        await self._exigir_estado_codificable(confirmacion.cuenta_medica_id)
        version_id, _ = await self._repositorio.version_vigente()
        candidato = await self._repositorio.obtener_candidato(
            version_id, confirmacion.codigo_elegido
        )
        if candidato is None:
            raise ErrorCodigoCpmsInexistente(
                f"El codigo {confirmacion.codigo_elegido!r} no existe en la version "
                f"vigente del catalogo CPMS ({version_id})."
            )

        fin = self._reloj.ahora()
        id_creado = await self._persistir(confirmacion, version_id, fin)
        await self._medir(confirmacion, actor, inicio_sugerencia, fin, version_id)
        return id_creado

    async def _exigir_estado_codificable(self, cuenta_medica_id: int) -> None:
        """Tabla 69: nada despues de CERRADA o ANULADA; tampoco se codifica
        una cuenta ya facturada o en manos de la IAFAS. Se codifica antes
        de facturar, al corregir una rechazada (T-05) y al refacturar por
        una glosa tecnica (CU-10)."""
        if self._estado_cuenta is None:
            return
        estado = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if estado not in ESTADOS_CODIFICABLES:
            raise ErrorCuentaNoCodificable(
                f"La cuenta {cuenta_medica_id} esta en estado {estado!r}: no admite codificacion."
            )

    async def _persistir(
        self, confirmacion: ConfirmacionCodigoCpms, version_id: int, fin: datetime
    ) -> int:
        origen = (
            "coincidencia_exacta" if confirmacion.posicion_aceptada is None else "sugerencia_tfidf"
        )
        return await self._repositorio.confirmar_codigo(
            DatosConfirmacionCodigo(
                cuenta_id=confirmacion.cuenta_medica_id,
                descripcion_registrada=confirmacion.descripcion_registrada,
                codigo_asignado=confirmacion.codigo_elegido,
                cpms_version_id=version_id,
                origen_codigo=origen,
                posicion_aceptada=confirmacion.posicion_aceptada,
                usuario_confirmo_id=confirmacion.usuario_confirmo_id,
                cantidad=confirmacion.cantidad,
                monto_unitario=confirmacion.monto_unitario,
                fecha=confirmacion.fecha,
                confirmado_en=fin,
            )
        )

    async def _medir(
        self,
        confirmacion: ConfirmacionCodigoCpms,
        actor: str,
        inicio_sugerencia: datetime,
        fin: datetime,
        version_id: int,
    ) -> None:
        # Duracion TOTAL hasta la confirmacion humana (Seccion 6.4), no
        # solo el computo del sistema: por eso `inicio_sugerencia` viene de
        # afuera, del instante en que se pidieron las sugerencias, no de
        # `self._reloj.ahora()` tomado aqui.
        await self._registro_mediciones.registrar(
            MedicionPaso(
                paso="codificacion_total",
                inicio=inicio_sugerencia,
                fin=fin,
                actor=actor,
                cuenta_medica_id=confirmacion.cuenta_medica_id,
                resultado="confirmado",
                datos={
                    "cpms_version_id": version_id,
                    "codigo_asignado": confirmacion.codigo_elegido,
                },
            )
        )


class ListarVersionesCpms:
    """Seccion 11: `GET /catalogo-cpms/versiones` (Fase 18)."""

    def __init__(self, repositorio: RepositorioCpms) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[VersionCpms]:
        return await self._repositorio.listar_versiones()
