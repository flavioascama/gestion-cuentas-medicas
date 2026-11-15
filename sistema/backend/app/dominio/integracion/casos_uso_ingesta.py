"""Casos de uso de la adenda de ingesta y completitud
(ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md), separados de casos_uso.py por
Seccion 3 (limite de 400 lineas por archivo) y porque cubren un contexto
distinto (alta de la cuenta, no consulta de trabajos)."""

from __future__ import annotations

from app.dominio.integracion.puertos_ingesta import (
    DatosNuevaCuenta,
    PiezaCompletitud,
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
    ResultadoCompletitud,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, RegistroEventos


class RegistrarCuentaMedica:
    """Adenda, punto 1: alta puntual de una cuenta desde la interfaz, sin
    pasar por el generador de datos sinteticos. Reemplaza cualquier
    proceso disperso y manual de captura (planilla, correo, etc.)."""

    def __init__(
        self, repositorio: RepositorioIngestaCuentas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, datos: DatosNuevaCuenta, actor: str) -> int:
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


# Piezas fijas de la adenda (punto 2 de la tabla): la de "paciente e IAFAS
# asignada" no se evalua contra la base de datos porque una cuenta_medica
# no puede existir sin ambos (columnas NOT NULL) -- siempre esta completa.
_ETIQUETA_PACIENTE = "Paciente e IAFAS asignada"
_ETIQUETA_COBERTURA = "Asegurado acreditado en ACREDITA SALUD"
_ETIQUETA_CODIFICACION = "Al menos un procedimiento confirmado (CPMS)"
_ETIQUETA_COMPROBANTE = "Comprobante de pago aceptado"


class ConsultarCompletitudCuenta:
    """Adenda, punto 2: por cada pieza que el flujo ya exige antes de
    generar un lote, dice si esta OK o FALTA, y la accion que la resuelve.

    Las cuatro piezas ya se pueden resolver de principio a fin: la de
    "comprobante de pago" se completa emitiendolo contra el simulador PSE
    (EmitirComprobantePago, app/dominio/pse/), agregado en esta misma
    adenda -- antes de eso no habia ninguna forma de completarla y esta
    consulta la reportaba con honestidad sin bloquear la transicion de
    abajo; ese caso ya no existe.

    Efecto secundario deliberado (no es una consulta pura): si las cuatro
    piezas ya estan OK y la cuenta sigue REGISTRADA, la marca FACTURADA
    aqui mismo. Es la unica transicion real que existe hoy hacia ese
    estado -- antes de esta adenda ningun caso de uso la producia (los
    datos sinteticos la fuerzan directo en la carga, sin pasar por
    negocio). Centralizar la transicion en la consulta de completitud, en
    vez de repartirla entre ConfirmarCodigoCpms, el robot de acreditacion
    y EmitirComprobantePago (tres contextos de dominio distintos), evita
    duplicar la regla en tres lugares; el costo es que la pantalla de
    detalle de cuenta debe volver a pedir la completitud tras cada accion
    para que la transicion se aplique, lo cual ya hace de forma natural
    (Seccion 4 de la adenda)."""

    def __init__(
        self, repositorio: RepositorioCompletitudCuenta, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_id: int, actor: str) -> ResultadoCompletitud | None:
        estado_piezas = await self._repositorio.obtener_estado_piezas(cuenta_id)
        if estado_piezas is None:
            return None

        cobertura_ok = estado_piezas.tiene_acreditacion
        codificacion_ok = estado_piezas.cantidad_procedimientos > 0
        comprobante_ok = estado_piezas.tiene_comprobante
        estado_cuenta = estado_piezas.estado_cuenta

        if estado_cuenta == "REGISTRADA" and cobertura_ok and codificacion_ok and comprobante_ok:
            await self._facturar(cuenta_id, actor)
            estado_cuenta = "FACTURADA"

        return ResultadoCompletitud(
            cuenta_id=cuenta_id,
            estado_cuenta=estado_cuenta,
            piezas=_construir_piezas(cobertura_ok, codificacion_ok, comprobante_ok),
        )

    async def _facturar(self, cuenta_id: int, actor: str) -> None:
        # T-02 (Tabla 58) validada por el motor (RF-08); el repositorio
        # conserva ademas su guarda `WHERE estado = 'REGISTRADA'`.
        validar_transicion("REGISTRADA", TipoTransicion.FACTURACION)
        await self._repositorio.marcar_facturada(cuenta_id)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CUENTA_FACTURADA",
                actor=actor,
                estado_previo="REGISTRADA",
                estado_nuevo="FACTURADA",
                datos={},
            )
        )


def _construir_piezas(
    cobertura_ok: bool, codificacion_ok: bool, comprobante_ok: bool
) -> tuple[PiezaCompletitud, ...]:
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
            accion=None if cobertura_ok else "verificar_cobertura",
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
