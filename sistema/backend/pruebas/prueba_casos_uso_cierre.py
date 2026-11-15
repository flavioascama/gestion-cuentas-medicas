"""Pruebas de los casos de uso de cierre y anulacion (CU-13, Seccion
5.2.4.1, Tabla 58 T-12/T-13; RF-21) con dobles de prueba -- sin
Postgres real: eso se verifica aparte (pruebas_integracion/)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pytest

from app.dominio.acceso.entidades import NombreRol
from app.dominio.cierre.casos_uso import (
    CerrarCuenta,
    ResolverSolicitudAnulacion,
    SolicitarAnulacion,
)
from app.dominio.cierre.errores import (
    ErrorDiferenciaPendiente,
    ErrorObservacionPendiente,
    ErrorSinLiquidacion,
    ErrorSolicitudAnulacionInexistente,
    ErrorSolicitudAnulacionYaPendiente,
    ErrorSolicitudAnulacionYaResuelta,
)
from app.dominio.cierre.valores import (
    DatosNuevaSolicitudAnulacion,
    EstadoSolicitudAnulacion,
    SolicitudAnulacion,
)
from app.dominio.liquidacion.valores import Liquidacion
from app.dominio.observaciones.valores import Naturaleza, Observacion
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.puertos_comunes import Evento, Observabilidad

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _MedicionesFalso:
    async def registrar(self, medicion: object) -> None:
        pass


def _observabilidad(registro_eventos: _RegistroEventosFalso) -> Observabilidad:
    return Observabilidad(eventos=registro_eventos, mediciones=_MedicionesFalso())


@dataclass
class _EstadoCuentaFalso:
    estados: dict[int, str]

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estados.get(cuenta_medica_id)

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        self.estados[cuenta_medica_id] = estado_nuevo


def _liquidacion(cuenta_medica_id: int, diferencia: Decimal | None) -> Liquidacion:
    return Liquidacion(
        id=1,
        cuenta_medica_id=cuenta_medica_id,
        es_parcial=False,
        monto_liquidado=Decimal("1500.00"),
        registrado_en=_AHORA,
        monto_pagado=None if diferencia is None else Decimal("1500.00") + diferencia,
        diferencia=diferencia,
        conciliado_en=None if diferencia is None else _AHORA,
    )


@dataclass
class _LiquidacionesFalso:
    """Solo implementa lo que CerrarCuenta necesita: `crear`/`conciliar`
    los prueba RegistrarLiquidacion/ConciliarPago aparte
    (pruebas/prueba_casos_uso_liquidacion.py)."""

    fila: Liquidacion | None

    async def crear(self, datos: object) -> int:
        raise NotImplementedError

    async def obtener_por_cuenta(self, cuenta_medica_id: int) -> Liquidacion | None:
        return self.fila

    async def conciliar(
        self, liquidacion_id: int, monto_pagado: object, diferencia: object, conciliado_en: object
    ) -> None:
        raise NotImplementedError


def _observacion(estado: str) -> Observacion:
    return Observacion(
        id=1,
        cuenta_medica_id=1,
        motivo_codigo="OBS-01",
        naturaleza=Naturaleza.ADMINISTRATIVA,
        es_parcial=False,
        detalle_campo_objetado=None,
        responsable_rol=NombreRol.ANALISTA,
        responsable_usuario_id=None,
        estado=estado,
        respuesta_texto=None,
        respuesta_sustento=None,
        registrado_en=_AHORA,
        respondido_en=None,
    )


@dataclass
class _ObservacionesFalso:
    """Solo implementa lo que CerrarCuenta necesita: el resto de
    RepositorioObservaciones lo prueba
    pruebas/prueba_casos_uso_observaciones.py."""

    filas: list[Observacion]

    async def crear(self, datos: object) -> int:
        raise NotImplementedError

    async def obtener(self, observacion_id: int) -> Observacion | None:
        raise NotImplementedError

    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[Observacion]:
        return self.filas

    async def reasignar(
        self,
        observacion_id: int,
        naturaleza: object,
        responsable_rol: object,
        responsable_usuario_id: object,
    ) -> None:
        raise NotImplementedError

    async def responder(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: object,
        respondido_en: object,
    ) -> None:
        raise NotImplementedError


# --- CerrarCuenta (CU-13, T-12) --------------------------------------------


async def prueba_cerrar_cuenta_sin_liquidacion_es_rechazado() -> None:
    caso_uso = CerrarCuenta(
        liquidaciones=_LiquidacionesFalso(None),
        observaciones=_ObservacionesFalso([]),
        estado_cuenta=_EstadoCuentaFalso({1: "PAGADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
    )
    with pytest.raises(ErrorSinLiquidacion):
        await caso_uso.ejecutar(1, actor="ana.analista")


async def prueba_cerrar_cuenta_con_diferencia_pendiente_es_rechazado() -> None:
    caso_uso = CerrarCuenta(
        liquidaciones=_LiquidacionesFalso(_liquidacion(1, Decimal("-50.00"))),
        observaciones=_ObservacionesFalso([]),
        estado_cuenta=_EstadoCuentaFalso({1: "PAGADA_PARCIAL"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
    )
    with pytest.raises(ErrorDiferenciaPendiente):
        await caso_uso.ejecutar(1, actor="ana.analista")


async def prueba_cerrar_cuenta_con_observacion_abierta_es_rechazado() -> None:
    caso_uso = CerrarCuenta(
        liquidaciones=_LiquidacionesFalso(_liquidacion(1, Decimal("0.00"))),
        observaciones=_ObservacionesFalso([_observacion("ABIERTA")]),
        estado_cuenta=_EstadoCuentaFalso({1: "PAGADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
    )
    with pytest.raises(ErrorObservacionPendiente):
        await caso_uso.ejecutar(1, actor="ana.analista")


async def prueba_cerrar_cuenta_pagada_sin_pendientes_la_cierra() -> None:
    estado_cuenta = _EstadoCuentaFalso({1: "PAGADA"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = CerrarCuenta(
        liquidaciones=_LiquidacionesFalso(_liquidacion(1, Decimal("0.00"))),
        observaciones=_ObservacionesFalso([_observacion("RESPONDIDA")]),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
    )
    estado_nuevo = await caso_uso.ejecutar(1, actor="ana.analista")

    assert estado_nuevo == "CERRADA"
    assert estado_cuenta.estados[1] == "CERRADA"
    assert registro_eventos.eventos[0].tipo_evento == "CIERRE"


# --- SolicitarAnulacion / ResolverSolicitudAnulacion (CU-13, T-13) --------


@dataclass
class _SolicitudesAnulacionFalso:
    siguiente_id: int = 1
    filas: dict[int, SolicitudAnulacion] = field(default_factory=dict)

    async def crear(self, datos: DatosNuevaSolicitudAnulacion) -> int:
        id_nuevo = self.siguiente_id
        self.siguiente_id += 1
        self.filas[id_nuevo] = SolicitudAnulacion(
            id=id_nuevo,
            cuenta_medica_id=datos.cuenta_medica_id,
            motivo=datos.motivo,
            estado=EstadoSolicitudAnulacion.PENDIENTE,
            solicitado_por=datos.solicitado_por,
            solicitado_en=datos.solicitado_en,
            resuelto_por=None,
            resuelto_en=None,
        )
        return id_nuevo

    async def obtener(self, solicitud_id: int) -> SolicitudAnulacion | None:
        return self.filas.get(solicitud_id)

    async def obtener_pendiente_por_cuenta(
        self, cuenta_medica_id: int
    ) -> SolicitudAnulacion | None:
        for fila in self.filas.values():
            if (
                fila.cuenta_medica_id == cuenta_medica_id
                and fila.estado == EstadoSolicitudAnulacion.PENDIENTE
            ):
                return fila
        return None

    async def resolver(
        self, solicitud_id: int, aprobada: bool, resuelto_por: str, resuelto_en: datetime
    ) -> None:
        actual = self.filas[solicitud_id]
        nuevo_estado = (
            EstadoSolicitudAnulacion.APROBADA if aprobada else EstadoSolicitudAnulacion.RECHAZADA
        )
        self.filas[solicitud_id] = SolicitudAnulacion(
            id=actual.id,
            cuenta_medica_id=actual.cuenta_medica_id,
            motivo=actual.motivo,
            estado=nuevo_estado,
            solicitado_por=actual.solicitado_por,
            solicitado_en=actual.solicitado_en,
            resuelto_por=resuelto_por,
            resuelto_en=resuelto_en,
        )


async def prueba_solicitar_anulacion_desde_estado_terminal_es_rechazado() -> None:
    caso_uso = SolicitarAnulacion(
        repositorio=_SolicitudesAnulacionFalso(),
        estado_cuenta=_EstadoCuentaFalso({1: "CERRADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorTransicionNoDefinida):
        await caso_uso.ejecutar(1, "duplicada", actor="ana.analista")


async def prueba_solicitar_anulacion_dos_veces_es_rechazado() -> None:
    repositorio = _SolicitudesAnulacionFalso()
    caso_uso = SolicitarAnulacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(1, "duplicada", actor="ana.analista")

    with pytest.raises(ErrorSolicitudAnulacionYaPendiente):
        await caso_uso.ejecutar(1, "otra vez", actor="ana.analista")


async def prueba_aprobar_anulacion_lleva_la_cuenta_a_anulada() -> None:
    repositorio = _SolicitudesAnulacionFalso()
    registro_eventos_solicitud = _RegistroEventosFalso()
    solicitud_id = await SolicitarAnulacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=_observabilidad(registro_eventos_solicitud),
        reloj=_RelojFijo(),
    ).ejecutar(1, "paciente no se presento", actor="ana.analista")

    estado_cuenta = _EstadoCuentaFalso({1: "FACTURADA"})
    registro_eventos = _RegistroEventosFalso()
    estado_nuevo = await ResolverSolicitudAnulacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    ).ejecutar(solicitud_id, aprobada=True, actor="jefa.prueba")

    assert estado_nuevo == "ANULADA"
    assert estado_cuenta.estados[1] == "ANULADA"
    assert registro_eventos.eventos[0].tipo_evento == "ANULACION"
    assert registro_eventos.eventos[0].estado_nuevo == "ANULADA"


async def prueba_rechazar_anulacion_no_toca_el_estado() -> None:
    repositorio = _SolicitudesAnulacionFalso()
    solicitud_id = await SolicitarAnulacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    ).ejecutar(1, "paciente no se presento", actor="ana.analista")

    estado_cuenta = _EstadoCuentaFalso({1: "FACTURADA"})
    registro_eventos = _RegistroEventosFalso()
    resultado = await ResolverSolicitudAnulacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    ).ejecutar(solicitud_id, aprobada=False, actor="jefa.prueba")

    assert resultado is None
    assert estado_cuenta.estados[1] == "FACTURADA"
    assert registro_eventos.eventos[0].tipo_evento == "ANULACION_RECHAZADA"


async def prueba_resolver_solicitud_inexistente_es_rechazado() -> None:
    caso_uso = ResolverSolicitudAnulacion(
        repositorio=_SolicitudesAnulacionFalso(),
        estado_cuenta=_EstadoCuentaFalso({}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorSolicitudAnulacionInexistente):
        await caso_uso.ejecutar(999, aprobada=True, actor="jefa.prueba")


async def prueba_resolver_solicitud_ya_resuelta_es_rechazado() -> None:
    repositorio = _SolicitudesAnulacionFalso()
    solicitud_id = await SolicitarAnulacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    ).ejecutar(1, "motivo", actor="ana.analista")
    caso_uso = ResolverSolicitudAnulacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "FACTURADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(solicitud_id, aprobada=False, actor="jefa.prueba")

    with pytest.raises(ErrorSolicitudAnulacionYaResuelta):
        await caso_uso.ejecutar(solicitud_id, aprobada=True, actor="jefa.prueba")
