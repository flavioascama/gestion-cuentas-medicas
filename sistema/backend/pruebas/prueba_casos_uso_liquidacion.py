"""Pruebas de los casos de uso de liquidacion y pago (CU-12, Seccion
5.2.4.1, Tabla 58 T-10/T-11) con dobles de prueba -- sin Postgres real:
eso se verifica aparte (pruebas/prueba_repositorio_liquidaciones.py y,
para el flujo completo, pruebas_integracion/)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pytest

from app.dominio.cierre.casos_uso import CerrarCuenta
from app.dominio.liquidacion.casos_uso import ConciliarPago, RegistrarLiquidacion
from app.dominio.liquidacion.errores import (
    ErrorLiquidacionInexistente,
    ErrorPagoExcedeSaldo,
    ErrorPagoYaConciliado,
)
from app.dominio.liquidacion.valores import DatosNuevaLiquidacion, Liquidacion
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


@dataclass
class _EstadoCuentaFalso:
    estados: dict[int, str]

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estados.get(cuenta_medica_id)

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        self.estados[cuenta_medica_id] = estado_nuevo


@dataclass
class _LiquidacionesFalso:
    siguiente_id: int = 1
    filas: dict[int, Liquidacion] = field(default_factory=dict)

    async def crear(self, datos: DatosNuevaLiquidacion) -> int:
        id_nuevo = self.siguiente_id
        self.siguiente_id += 1
        self.filas[id_nuevo] = Liquidacion(
            id=id_nuevo,
            cuenta_medica_id=datos.cuenta_medica_id,
            es_parcial=datos.es_parcial,
            monto_liquidado=datos.monto_liquidado,
            registrado_en=datos.registrado_en,
            monto_pagado=None,
            diferencia=None,
            conciliado_en=None,
        )
        return id_nuevo

    async def obtener_por_cuenta(self, cuenta_medica_id: int) -> Liquidacion | None:
        for fila in self.filas.values():
            if fila.cuenta_medica_id == cuenta_medica_id:
                return fila
        return None

    async def conciliar(
        self,
        liquidacion_id: int,
        monto_pagado: Decimal,
        diferencia: Decimal,
        conciliado_en: datetime,
    ) -> None:
        actual = self.filas[liquidacion_id]
        self.filas[liquidacion_id] = Liquidacion(
            id=actual.id,
            cuenta_medica_id=actual.cuenta_medica_id,
            es_parcial=actual.es_parcial,
            monto_liquidado=actual.monto_liquidado,
            registrado_en=actual.registrado_en,
            monto_pagado=monto_pagado,
            diferencia=diferencia,
            conciliado_en=conciliado_en,
        )

    async def registrar_pago_adicional(
        self, liquidacion_id: int, monto_pagado: Decimal, diferencia: Decimal
    ) -> None:
        actual = self.filas[liquidacion_id]
        await self.conciliar(liquidacion_id, monto_pagado, diferencia, actual.conciliado_en)  # type: ignore[arg-type]


def _observabilidad(registro_eventos: _RegistroEventosFalso) -> Observabilidad:
    return Observabilidad(eventos=registro_eventos, mediciones=_MedicionesFalso())


# --- RegistrarLiquidacion (CU-12, T-10) -----------------------------------


async def prueba_registrar_liquidacion_total_desde_en_auditoria() -> None:
    estado_cuenta = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = RegistrarLiquidacion(
        repositorio=_LiquidacionesFalso(),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(1, Decimal("1500.00"), actor="tesoreria.prueba")

    assert resultado.estado_cuenta == "LIQUIDADA"
    assert estado_cuenta.estados[1] == "LIQUIDADA"
    assert registro_eventos.eventos[0].tipo_evento == "LIQUIDACION"
    assert registro_eventos.eventos[0].estado_previo == "EN_AUDITORIA"
    assert registro_eventos.eventos[0].estado_nuevo == "LIQUIDADA"


async def prueba_registrar_liquidacion_parcial_desde_glosada_parcial() -> None:
    estado_cuenta = _EstadoCuentaFalso({1: "GLOSADA_PARCIAL"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = RegistrarLiquidacion(
        repositorio=_LiquidacionesFalso(),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(1, Decimal("800.00"), actor="tesoreria.prueba")

    assert resultado.estado_cuenta == "LIQUIDADA_PARCIAL"
    assert registro_eventos.eventos[0].tipo_evento == "LIQUIDACION_PARCIAL"


async def prueba_registrar_liquidacion_desde_estado_invalido_es_rechazado() -> None:
    caso_uso = RegistrarLiquidacion(
        repositorio=_LiquidacionesFalso(),
        estado_cuenta=_EstadoCuentaFalso({1: "REGISTRADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorTransicionNoDefinida):
        await caso_uso.ejecutar(1, Decimal("100.00"), actor="tesoreria.prueba")


async def prueba_registrar_liquidacion_dos_veces_es_rechazado_por_el_motor() -> None:
    """Tabla 58: ninguna fila admite T-10 otra vez desde LIQUIDADA o
    LIQUIDADA_PARCIAL -- el motor ya rechaza una segunda liquidacion de
    la misma cuenta por su cuenta, sin que el caso de uso necesite su
    propia guarda contra duplicados."""

    estado_cuenta = _EstadoCuentaFalso({1: "LIQUIDADA"})
    caso_uso = RegistrarLiquidacion(
        repositorio=_LiquidacionesFalso(),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorTransicionNoDefinida):
        await caso_uso.ejecutar(1, Decimal("100.00"), actor="tesoreria.prueba")


# --- ConciliarPago (CU-12, T-11) ------------------------------------------


async def prueba_conciliar_pago_sin_liquidacion_es_rechazado() -> None:
    caso_uso = ConciliarPago(
        repositorio=_LiquidacionesFalso(),
        estado_cuenta=_EstadoCuentaFalso({1: "LIQUIDADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorLiquidacionInexistente):
        await caso_uso.ejecutar(1, Decimal("1500.00"), actor="tesoreria.prueba")


async def prueba_conciliar_pago_exacto_lleva_la_cuenta_a_pagada() -> None:
    repositorio = _LiquidacionesFalso()
    await repositorio.crear(
        DatosNuevaLiquidacion(
            cuenta_medica_id=1,
            es_parcial=False,
            monto_liquidado=Decimal("1500.00"),
            registrado_en=_AHORA,
        )
    )
    estado_cuenta = _EstadoCuentaFalso({1: "LIQUIDADA"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ConciliarPago(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(1, Decimal("1500.00"), actor="tesoreria.prueba")

    assert resultado.estado_cuenta == "PAGADA"
    assert resultado.diferencia == Decimal("0.00")
    assert estado_cuenta.estados[1] == "PAGADA"
    assert registro_eventos.eventos[0].tipo_evento == "CONCILIACION_PAGO"


async def prueba_conciliar_pago_con_diferencia_registra_la_diferencia_y_avanza() -> None:
    """Tabla 51, flujo alternativo: "si el pago difiere del monto
    liquidado, el sistema registra la diferencia y la incorpora al
    seguimiento de la cartera por cobrar" -- la conciliacion avanza
    igual, no se rechaza."""

    repositorio = _LiquidacionesFalso()
    await repositorio.crear(
        DatosNuevaLiquidacion(
            cuenta_medica_id=1,
            es_parcial=True,
            monto_liquidado=Decimal("800.00"),
            registrado_en=_AHORA,
        )
    )
    estado_cuenta = _EstadoCuentaFalso({1: "LIQUIDADA_PARCIAL"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ConciliarPago(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(1, Decimal("750.00"), actor="tesoreria.prueba")

    assert resultado.estado_cuenta == "PAGADA_PARCIAL"
    assert resultado.diferencia == Decimal("-50.00")
    assert registro_eventos.eventos[0].tipo_evento == "CONCILIACION_PAGO_PARCIAL"


async def prueba_conciliar_pago_dos_veces_es_rechazado() -> None:
    repositorio = _LiquidacionesFalso()
    await repositorio.crear(
        DatosNuevaLiquidacion(
            cuenta_medica_id=1,
            es_parcial=False,
            monto_liquidado=Decimal("1500.00"),
            registrado_en=_AHORA,
        )
    )
    caso_uso = ConciliarPago(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "LIQUIDADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(1, Decimal("1500.00"), actor="tesoreria.prueba")

    with pytest.raises(ErrorPagoYaConciliado):
        await caso_uso.ejecutar(1, Decimal("1500.00"), actor="tesoreria.prueba")


# --- Pago adicional (cuenta pagada de menos) -------------------------------


class _SinObservacionesFalso:
    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[object]:
        return []


async def _cuenta_pagada_de_menos() -> tuple[_LiquidacionesFalso, _EstadoCuentaFalso]:
    repositorio = _LiquidacionesFalso()
    await repositorio.crear(
        DatosNuevaLiquidacion(
            cuenta_medica_id=1,
            es_parcial=False,
            monto_liquidado=Decimal("1500.00"),
            registrado_en=_AHORA,
        )
    )
    estado_cuenta = _EstadoCuentaFalso({1: "LIQUIDADA"})
    caso_uso = ConciliarPago(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(1, Decimal("1000.00"), actor="tesoreria.prueba")
    return repositorio, estado_cuenta


async def prueba_pago_adicional_hasta_diferencia_cero_permite_cerrar() -> None:
    repositorio, estado_cuenta = await _cuenta_pagada_de_menos()
    registro_eventos = _RegistroEventosFalso()
    observabilidad = _observabilidad(registro_eventos)
    caso_uso = ConciliarPago(repositorio, estado_cuenta, observabilidad, _RelojFijo())

    resultado = await caso_uso.ejecutar(1, Decimal("200.00"), actor="tesoreria.prueba")
    assert resultado.diferencia == Decimal("-300.00")
    resultado = await caso_uso.ejecutar(1, Decimal("300.00"), actor="tesoreria.prueba")

    assert resultado.estado_cuenta == "PAGADA"
    assert resultado.diferencia == Decimal("0.00")
    liquidacion = await repositorio.obtener_por_cuenta(1)
    assert liquidacion is not None
    assert liquidacion.monto_pagado == Decimal("1500.00")
    assert estado_cuenta.estados[1] == "PAGADA"
    evento = registro_eventos.eventos[-1]
    assert evento.tipo_evento == "PAGO_ADICIONAL_REGISTRADO"
    assert (evento.estado_previo, evento.estado_nuevo) == (None, None)
    assert evento.datos["monto_pago"] == "300.00"
    assert evento.datos["monto_pagado_acumulado"] == "1500.00"

    cierre = CerrarCuenta(repositorio, _SinObservacionesFalso(), estado_cuenta, observabilidad)  # type: ignore[arg-type]
    assert await cierre.ejecutar(1, actor="analista.prueba") == "CERRADA"


async def prueba_pago_adicional_sin_saldo_pendiente_es_rechazado() -> None:
    repositorio, estado_cuenta = await _cuenta_pagada_de_menos()
    caso_uso = ConciliarPago(
        repositorio, estado_cuenta, _observabilidad(_RegistroEventosFalso()), _RelojFijo()
    )
    await caso_uso.ejecutar(1, Decimal("500.00"), actor="tesoreria.prueba")

    with pytest.raises(ErrorPagoYaConciliado):
        await caso_uso.ejecutar(1, Decimal("10.00"), actor="tesoreria.prueba")


async def prueba_pago_adicional_no_supera_lo_que_falta_por_pagar() -> None:
    # Faltan 500.00: un pago mayor dejaria una diferencia sin forma de regularizar.
    repositorio, estado_cuenta = await _cuenta_pagada_de_menos()
    caso_uso = ConciliarPago(
        repositorio, estado_cuenta, _observabilidad(_RegistroEventosFalso()), _RelojFijo()
    )

    with pytest.raises(ErrorPagoExcedeSaldo):
        await caso_uso.ejecutar(1, Decimal("500.01"), actor="tesoreria.prueba")

    liquidacion = await repositorio.obtener_por_cuenta(1)
    assert liquidacion is not None
    assert liquidacion.monto_pagado == Decimal("1000.00")
