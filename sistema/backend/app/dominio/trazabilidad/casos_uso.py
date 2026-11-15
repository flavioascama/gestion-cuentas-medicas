"""Casos de uso del modulo de trazabilidad con panel de control
gerencial: CU-14 (consultar el historial), CU-15 (visualizar los
indicadores del ciclo) y CU-16 (exportar el expediente de auditoria),
Seccion 6.2 / Tabla 52.

CU-14 y CU-16 registran su propio acceso como un evento mas (RT-08,
control C-08): "inicio de sesion y accesos a datos sensibles, incluidas
las consultas y las exportaciones" se lee directo del almacen de
eventos -- la bitacora de accesos no es una tabla aparte, es el mismo
`evento` filtrado a ese conjunto de tipos (ver docs/DECISIONES.md,
Fase 29)."""

from __future__ import annotations

from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj
from app.dominio.trazabilidad.errores import ErrorCuentaInexistente, ErrorLoteInexistente
from app.dominio.trazabilidad.puertos import RepositorioTrazabilidad
from app.dominio.trazabilidad.valores import (
    Expediente,
    FiltroIndicadores,
    HistorialCuenta,
    HistorialLote,
    IndicadoresCiclo,
)


class ConsultarHistorialCuenta:
    """CU-14 (RF-14, RF-20): "el jefe selecciona la cuenta; el sistema
    reconstruye su historial... y registra la consulta en la bitacora
    de accesos". Si la cadena esta rota, "el sistema lo indica en la
    consulta y emite una alerta" -- el evento mismo es la alerta."""

    def __init__(
        self,
        repositorio: RepositorioTrazabilidad,
        observabilidad: Observabilidad,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad

    async def ejecutar(self, cuenta_medica_id: int, actor: str) -> HistorialCuenta:
        if not await self._repositorio.existe_cuenta(cuenta_medica_id):
            raise ErrorCuentaInexistente(f"No existe la cuenta medica {cuenta_medica_id}.")

        historial = await self._repositorio.historial_de_cuenta(cuenta_medica_id)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="HISTORIAL_CONSULTADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
            )
        )
        if not historial.cadena_integra:
            # Control C-15 (gestion de incidentes): la alerta en si es
            # este evento -- queda registrada y visible para el jefe y
            # el administrador sin depender de un canal externo.
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=cuenta_medica_id,
                    tipo_evento="RUPTURA_CADENA_DETECTADA",
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"rupturas": historial.rupturas},
                )
            )
        return historial


class ConsultarHistorialLote:
    """RT-13: el historial de un lote (generacion, validacion, remision,
    respuesta de la IAFAS, envio a SUSALUD), con la misma verificacion de
    cadena y el mismo registro en la bitacora que el de la cuenta."""

    def __init__(
        self, repositorio: RepositorioTrazabilidad, observabilidad: Observabilidad
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad

    async def ejecutar(self, lote_id: int, actor: str) -> HistorialLote:
        if not await self._repositorio.existe_lote(lote_id):
            raise ErrorLoteInexistente(f"No existe el lote {lote_id}.")
        historial = await self._repositorio.historial_de_lote(lote_id)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento="HISTORIAL_CONSULTADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
            )
        )
        if not historial.cadena_integra:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=None,
                    lote_id=lote_id,
                    tipo_evento="RUPTURA_CADENA_DETECTADA",
                    actor=actor,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"rupturas": historial.rupturas},
                )
            )
        return historial


class VisualizarIndicadoresCiclo:
    """CU-15 (RF-15): panel de control gerencial. Consulta de solo
    lectura -- no genera ningun evento, igual que cualquier otra
    proyeccion derivada del almacen de eventos."""

    def __init__(self, repositorio: RepositorioTrazabilidad, reloj: Reloj) -> None:
        self._repositorio = repositorio
        self._reloj = reloj

    async def ejecutar(self, filtro: FiltroIndicadores) -> IndicadoresCiclo:
        return await self._repositorio.calcular_indicadores(filtro, self._reloj.ahora())


class ExportarExpediente:
    """CU-16 (RF-17, RF-20): "el jefe solicita la exportacion y
    registra su motivo; el sistema genera el expediente... y registra
    la exportacion en la bitacora de accesos"."""

    def __init__(
        self,
        repositorio: RepositorioTrazabilidad,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, motivo: str, actor: str) -> Expediente:
        if not await self._repositorio.existe_cuenta(cuenta_medica_id):
            raise ErrorCuentaInexistente(f"No existe la cuenta medica {cuenta_medica_id}.")

        historial = await self._repositorio.historial_de_cuenta(cuenta_medica_id)
        documentos = await self._repositorio.documentos_de_cuenta(cuenta_medica_id)
        ahora = self._reloj.ahora()
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="EXPEDIENTE_EXPORTADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"motivo": motivo},
            )
        )
        return Expediente(
            cuenta_medica_id=cuenta_medica_id,
            historial=historial,
            documentos=documentos,
            generado_en=ahora,
        )
