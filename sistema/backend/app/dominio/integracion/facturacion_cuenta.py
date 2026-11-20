"""La cuenta pasa a FACTURADA al completarse sus piezas (2026-11-19).

La regla de completitud vive aqui, en un solo lugar: la usan la consulta
de completitud (que solo lee) y FacturarCuentaCompleta, que aplica la
transicion T-02 en la misma operacion que completa la ultima pieza y a
nombre de quien la realizo. El comprobante exige ya la cobertura, el
diagnostico y los procedimientos codificados, asi que en la practica esa
operacion es el registro del comprobante (EmitirComprobantePago). Antes la
transicion la hacia la consulta de completitud, a nombre de quien abria la
pantalla."""

from __future__ import annotations

from app.dominio.integracion.puertos_ingesta import (
    EstadoPiezasCuenta,
    RepositorioCompletitudCuenta,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, RegistroEventos

ESTADO_REGISTRADA = "REGISTRADA"
ESTADO_FACTURADA = "FACTURADA"


def cobertura(estado: EstadoPiezasCuenta) -> tuple[bool, str | None]:
    """La pieza de cobertura y su accion: el asegurado acreditado y, en una
    hospitalizacion, la carta de garantia registrada."""
    if not (estado.tiene_acreditacion and estado.acreditable) or estado.cobertura_no_conforme:
        return False, "verificar_cobertura"
    if estado.exige_carta_garantia and not estado.tiene_carta_garantia:
        return False, "registrar_carta_garantia"
    return True, None


def codificacion_completa(estado: EstadoPiezasCuenta) -> bool:
    # Ninguno de los procedimientos importados puede quedar sin codigo.
    return estado.cantidad_procedimientos > 0 and estado.procedimientos_por_codificar == 0


def cuenta_completa(estado: EstadoPiezasCuenta) -> bool:
    return (
        cobertura(estado)[0]
        and estado.tiene_diagnostico
        and codificacion_completa(estado)
        and estado.tiene_comprobante
    )


class FacturarCuentaCompleta:
    """T-02 (Tabla 58): una cuenta REGISTRADA con todas sus piezas pasa a
    FACTURADA, con el evento CUENTA_FACTURADA a nombre del actor. Si la
    cuenta no esta REGISTRADA o le falta una pieza, no hace nada: se puede
    llamar mas de una vez sin efecto adicional."""

    def __init__(
        self, repositorio: RepositorioCompletitudCuenta, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_id: int, actor: str) -> bool:
        """True si la cuenta paso a FACTURADA en esta llamada."""
        estado = await self._repositorio.obtener_estado_piezas(cuenta_id)
        if estado is None or estado.estado_cuenta != ESTADO_REGISTRADA:
            return False
        if not cuenta_completa(estado):
            return False
        # Validada por el motor (RF-08); el repositorio conserva ademas su
        # guarda `WHERE estado = 'REGISTRADA'`.
        validar_transicion(ESTADO_REGISTRADA, TipoTransicion.FACTURACION)
        await self._repositorio.marcar_facturada(cuenta_id)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CUENTA_FACTURADA",
                actor=actor,
                estado_previo=ESTADO_REGISTRADA,
                estado_nuevo=ESTADO_FACTURADA,
                datos={},
            )
        )
        return True
