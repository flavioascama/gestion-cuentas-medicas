"""La observacion guarda cuanto se observo y en que termino (2026-11-19):
el monto glosado y el resultado LEVANTADA (la liquidacion de una cuenta
SUBSANADA) o MANTENIDA (una observacion nueva sobre una cuenta SUBSANADA).
Reusa los dobles de prueba_casos_uso_observaciones.py."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.liquidacion.casos_uso import RegistrarLiquidacion
from app.dominio.observaciones.casos_uso import RegistrarObservacion, ResponderObservacion
from app.dominio.observaciones.valores import (
    DatosNuevaObservacion,
    DatosRegistroObservacion,
    Naturaleza,
    ResultadoObservacion,
)
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioObservacionesSql,
)
from pruebas.prueba_casos_uso_liquidacion import _LiquidacionesFalso
from pruebas.prueba_casos_uso_observaciones import (
    _AHORA,
    _MOTIVO_ADMINISTRATIVA,
    _CatalogoMotivosFalso,
    _EstadoCuentaFalso,
    _observabilidad,
    _ObservacionesFalso,
    _RegistroEventosFalso,
    _RelojFijo,
)
from pruebas.prueba_comunicaciones_iafas import _armar, _Casos, _comunicacion, _RepositorioFalso
from pruebas.prueba_repositorio_observaciones import _sembrar_cuenta, _sembrar_motivo


def _registrar(
    repositorio: _ObservacionesFalso, estado: _EstadoCuentaFalso
) -> RegistrarObservacion:
    return RegistrarObservacion(
        repositorio=repositorio,
        catalogo=_CatalogoMotivosFalso({"OBS-01": _MOTIVO_ADMINISTRATIVA}),
        estado_cuenta=estado,
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )


def _datos(monto: Decimal | None = None) -> DatosRegistroObservacion:
    return DatosRegistroObservacion(
        cuenta_medica_id=1,
        motivo_codigo="OBS-01",
        es_parcial=False,
        detalle_campo_objetado=None,
        actor="robot",
        monto_observado=monto,
    )


async def _glosada_y_respondida() -> tuple[_ObservacionesFalso, _EstadoCuentaFalso]:
    repositorio = _ObservacionesFalso()
    estado = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    await _registrar(repositorio, estado).ejecutar(_datos(Decimal("250.00")))
    await ResponderObservacion(
        repositorio, estado, _observabilidad(_RegistroEventosFalso()), _RelojFijo()
    ).ejecutar(1, "Se adjunta sustento", None, "ana")
    return repositorio, estado


async def prueba_el_monto_observado_se_guarda_con_la_observacion() -> None:
    repositorio = _ObservacionesFalso()
    capturados: list[DatosNuevaObservacion] = []
    crear_original = repositorio.crear

    async def crear(datos: DatosNuevaObservacion) -> int:
        capturados.append(datos)
        return await crear_original(datos)

    repositorio.crear = crear  # type: ignore[method-assign]
    await _registrar(repositorio, _EstadoCuentaFalso({1: "EN_AUDITORIA"})).ejecutar(
        _datos(Decimal("250.00"))
    )

    assert capturados[0].monto_observado == Decimal("250.00")


async def prueba_nueva_observacion_sobre_subsanada_deja_mantenida_la_respondida() -> None:
    repositorio, estado = await _glosada_y_respondida()
    assert estado.estados[1] == "SUBSANADA"

    await _registrar(repositorio, estado).ejecutar(_datos())

    assert repositorio.filas[1].resultado == ResultadoObservacion.MANTENIDA.value
    assert repositorio.filas[1].resultado_en == _AHORA
    assert repositorio.filas[2].resultado is None
    assert estado.estados[1] == "GLOSADA"


async def prueba_liquidacion_de_cuenta_subsanada_deja_levantada_la_respondida() -> None:
    repositorio, estado = await _glosada_y_respondida()

    await RegistrarLiquidacion(
        _LiquidacionesFalso(),
        estado,
        _observabilidad(_RegistroEventosFalso()),
        _RelojFijo(),
        repositorio,
    ).ejecutar(1, Decimal("1000.00"), "robot")

    assert repositorio.filas[1].resultado == ResultadoObservacion.LEVANTADA.value
    assert estado.estados[1] == "LIQUIDADA"


async def prueba_liquidacion_parcial_no_fija_resultado() -> None:
    """GLOSADA_PARCIAL -> LIQUIDADA_PARCIAL no dice si se acepto la respuesta."""
    repositorio = _ObservacionesFalso()
    estado = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    await _registrar(repositorio, estado).ejecutar(replace(_datos(), es_parcial=True))
    await ResponderObservacion(
        repositorio, estado, _observabilidad(_RegistroEventosFalso()), _RelojFijo()
    ).ejecutar(1, "Respuesta", None, "ana")

    await RegistrarLiquidacion(
        _LiquidacionesFalso(),
        estado,
        _observabilidad(_RegistroEventosFalso()),
        _RelojFijo(),
        repositorio,
    ).ejecutar(1, Decimal("600.00"), "robot")

    assert estado.estados[1] == "LIQUIDADA_PARCIAL"
    assert repositorio.filas[1].resultado is None


async def prueba_repositorio_guarda_monto_y_fija_resultado_solo_a_las_respondidas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        await _sembrar_motivo(sesion)
        repositorio = RepositorioObservacionesSql(sesion)
        datos = DatosNuevaObservacion(
            cuenta_medica_id=cuenta_id,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
            monto_observado=Decimal("120.50"),
        )
        respondida = await repositorio.crear(datos)
        abierta = await repositorio.crear(replace(datos, monto_observado=None))
        await repositorio.responder(respondida, "Respuesta", None, _AHORA)

        fijadas = await repositorio.fijar_resultado(
            cuenta_id, ResultadoObservacion.LEVANTADA, _AHORA
        )
        otra_vez = await repositorio.fijar_resultado(
            cuenta_id, ResultadoObservacion.MANTENIDA, _AHORA
        )
        filas = {o.id: o for o in await repositorio.listar_por_cuenta(cuenta_id)}

    assert fijadas == [respondida]
    assert otra_vez == []
    assert filas[respondida].monto_observado == Decimal("120.50")
    assert filas[respondida].resultado == "LEVANTADA"
    assert filas[abierta].resultado is None
    assert filas[abierta].monto_observado is None


async def prueba_la_glosa_de_la_aseguradora_trae_el_monto_observado() -> None:
    casos = _Casos()
    caso_uso, _ = _armar(_RepositorioFalso(documentos={"F00100000123": 5}), casos)
    datos = {"motivo_codigo": "ADM-01", "es_parcial": True, "monto_glosado": "40.00"}

    await caso_uso.ejecutar(_comunicacion("OBSERVACION", datos))
    sin_monto = _Casos()
    caso_sin_monto, _ = _armar(_RepositorioFalso(documentos={"F00100000123": 5}), sin_monto)
    await caso_sin_monto.ejecutar(_comunicacion("OBSERVACION", {"motivo_codigo": "ADM-01"}))

    assert casos.observacion.llamadas[0][0].monto_observado == Decimal("40.00")
    assert sin_monto.observacion.llamadas[0][0].monto_observado is None
