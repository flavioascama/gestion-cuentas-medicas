"""Casos de uso de la adenda de ingesta y completitud
(ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md), separados de casos_uso.py por
Seccion 3 (limite de 400 lineas por archivo) y porque cubren un contexto
distinto (alta de la cuenta, no consulta de trabajos)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.compartido.fecha_peru import fecha_peru
from app.dominio.integracion.diagnostico_cuenta import ErrorCie10Inexistente, normalizar_cie10
from app.dominio.integracion.facturacion_cuenta import cobertura, codificacion_completa
from app.dominio.integracion.puertos_ingesta import (
    AseguradoRegistrado,
    DatosNuevaCuenta,
    PiezaCompletitud,
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
    ResultadoCompletitud,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

MENSAJE_NOMBRES_EN_BLANCO = "Ingrese los nombres y los apellidos del asegurado."


class ErrorDatosNuevaCuenta(Exception):
    """Un dato de la nueva cuenta que impide registrarla."""


def nombres_recortados(nombres: str, apellidos: str) -> tuple[str, str] | None:
    """Nombres y apellidos sin espacios sobrantes; None si alguno queda en blanco."""
    nombres, apellidos = nombres.strip(), apellidos.strip()
    return (nombres, apellidos) if nombres and apellidos else None


def _validar_datos(datos: DatosNuevaCuenta, ahora: datetime) -> DatosNuevaCuenta:
    nombres = nombres_recortados(datos.nombres_asegurado, datos.apellidos_asegurado)
    if nombres is None:
        raise ErrorDatosNuevaCuenta(MENSAJE_NOMBRES_EN_BLANCO)
    # Con una prestacion futura ningun procedimiento se podria codificar.
    if datos.fecha_prestacion > fecha_peru(ahora):
        raise ErrorDatosNuevaCuenta("La fecha de prestación no puede ser posterior a hoy.")
    return replace(datos, nombres_asegurado=nombres[0], apellidos_asegurado=nombres[1])


class RegistrarCuentaMedica:
    """Adenda, punto 1: alta puntual de una cuenta desde la interfaz, sin
    pasar por el generador de datos sinteticos. Reemplaza cualquier
    proceso disperso y manual de captura (planilla, correo, etc.)."""

    def __init__(
        self,
        repositorio: RepositorioIngestaCuentas,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, datos: DatosNuevaCuenta, actor: str) -> int:
        datos = _validar_datos(datos, self._reloj.ahora())
        # El diagnostico es opcional, pero si viene debe estar en el catalogo,
        # igual que al registrarlo despues (RegistrarDiagnosticoPrincipal).
        codigo = normalizar_cie10(datos.diagnostico_principal_cie10 or "")
        if codigo and not await self._repositorio.existe_cie10(codigo):
            raise ErrorCie10Inexistente(codigo)
        datos = replace(datos, diagnostico_principal_cie10=codigo or None)
        # T-01 (Tabla 58) validada por el motor como el resto (RF-08).
        estado_inicial = validar_transicion(None, TipoTransicion.REGISTRO)
        cuenta_id = await self._repositorio.crear_cuenta(datos)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CUENTA_REGISTRADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=estado_inicial,
                datos={"iafas_id": datos.iafas_id},
            )
        )
        return cuenta_id


class BuscarAseguradoRegistrado:
    """Al registrar una cuenta (2026-11-18): con el documento, devuelve
    los nombres y la IAFAS del asegurado si la clinica ya lo atendio, para
    no volver a escribirlos. Un asegurado nuevo se escribe una sola vez:
    queda registrado al crear su primera cuenta."""

    def __init__(self, repositorio: RepositorioIngestaCuentas) -> None:
        self._repositorio = repositorio

    async def ejecutar(
        self, tipo_documento: str, numero_documento: str
    ) -> AseguradoRegistrado | None:
        return await self._repositorio.buscar_asegurado(
            tipo_documento.strip(), numero_documento.strip()
        )


# Piezas fijas de la adenda (punto 2 de la tabla): la de "paciente e IAFAS
# asignada" no se evalua contra la base de datos porque una cuenta_medica
# no puede existir sin ambos (columnas NOT NULL) -- siempre esta completa.
_ETIQUETA_PACIENTE = "Paciente e IAFAS asignada"
_ETIQUETA_COBERTURA = "Asegurado acreditado en ACREDITA SALUD"
_ETIQUETA_DIAGNOSTICO = "Diagnóstico principal (CIE-10)"
_ETIQUETA_CODIFICACION = "Al menos un procedimiento confirmado (CPMS)"
_ETIQUETA_COMPROBANTE = "Comprobante de pago aceptado"


class ConsultarCompletitudCuenta:
    """Adenda, punto 2: por cada pieza que el flujo ya exige antes de
    generar un lote, dice si esta OK o FALTA, y la accion que la resuelve.

    Solo lee (2026-11-19): la cuenta pasa a FACTURADA en la operacion que
    completa su ultima pieza (FacturarCuentaCompleta, en
    facturacion_cuenta.py), no cuando alguien abre la pantalla."""

    def __init__(self, repositorio: RepositorioCompletitudCuenta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_id: int) -> ResultadoCompletitud | None:
        estado_piezas = await self._repositorio.obtener_estado_piezas(cuenta_id)
        if estado_piezas is None:
            return None

        diagnostico_ok = estado_piezas.tiene_diagnostico
        return ResultadoCompletitud(
            cuenta_id=cuenta_id,
            estado_cuenta=estado_piezas.estado_cuenta,
            piezas=(
                *_construir_piezas(
                    cobertura(estado_piezas),
                    codificacion_completa(estado_piezas),
                    estado_piezas.tiene_comprobante,
                ),
                PiezaCompletitud(
                    clave="diagnostico",
                    etiqueta=_ETIQUETA_DIAGNOSTICO,
                    completa=diagnostico_ok,
                    bloquea=True,
                    accion=None if diagnostico_ok else "registrar_diagnostico",
                ),
            ),
            lote=estado_piezas.lote,
        )


def _construir_piezas(
    cobertura: tuple[bool, str | None], codificacion_ok: bool, comprobante_ok: bool
) -> tuple[PiezaCompletitud, ...]:
    cobertura_ok, accion_cobertura = cobertura
    return (
        PiezaCompletitud(
            clave="paciente_iafas",
            etiqueta=_ETIQUETA_PACIENTE,
            completa=True,
            bloquea=True,
            accion=None,
        ),
        PiezaCompletitud(
            clave="cobertura",
            etiqueta=_ETIQUETA_COBERTURA,
            completa=cobertura_ok,
            bloquea=True,
            accion=accion_cobertura,
        ),
        PiezaCompletitud(
            clave="codificacion",
            etiqueta=_ETIQUETA_CODIFICACION,
            completa=codificacion_ok,
            bloquea=True,
            accion=None if codificacion_ok else "codificar",
        ),
        PiezaCompletitud(
            clave="comprobante",
            etiqueta=_ETIQUETA_COMPROBANTE,
            completa=comprobante_ok,
            bloquea=True,
            accion=None if comprobante_ok else "emitir_comprobante",
        ),
    )
