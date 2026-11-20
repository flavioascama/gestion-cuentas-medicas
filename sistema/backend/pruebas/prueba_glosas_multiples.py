"""Pruebas de varias observaciones sobre una misma cuenta (2026-11-18):
una glosa adicional sobre una cuenta ya glosada se registra sin mover el
estado, y la respuesta lleva la cuenta a SUBSANADA solo cuando ya no le
queda ninguna otra ABIERTA. Reusa los dobles de
prueba_casos_uso_observaciones.py (ese archivo ya supera las 400 lineas)."""

from __future__ import annotations

from app.dominio.observaciones.casos_uso import RegistrarObservacion, ResponderObservacion
from app.dominio.observaciones.valores import DatosRegistroObservacion
from pruebas.prueba_casos_uso_observaciones import (
    _MOTIVO_ADMINISTRATIVA,
    _MOTIVO_TECNICA,
    _CatalogoMotivosFalso,
    _EstadoCuentaFalso,
    _observabilidad,
    _ObservacionesFalso,
    _RegistroEventosFalso,
    _RelojFijo,
)


def _registrar(
    repositorio: _ObservacionesFalso,
    estado_cuenta: _EstadoCuentaFalso,
    eventos: _RegistroEventosFalso,
) -> RegistrarObservacion:
    return RegistrarObservacion(
        repositorio=repositorio,
        catalogo=_CatalogoMotivosFalso(
            {"OBS-01": _MOTIVO_ADMINISTRATIVA, "OBS-04": _MOTIVO_TECNICA}
        ),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(eventos),
        reloj=_RelojFijo(),
    )


def _responder(
    repositorio: _ObservacionesFalso,
    estado_cuenta: _EstadoCuentaFalso,
    eventos: _RegistroEventosFalso,
) -> ResponderObservacion:
    return ResponderObservacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(eventos),
        reloj=_RelojFijo(),
    )


def _datos(motivo: str, es_parcial: bool) -> DatosRegistroObservacion:
    return DatosRegistroObservacion(
        cuenta_medica_id=1,
        motivo_codigo=motivo,
        es_parcial=es_parcial,
        detalle_campo_objetado=None,
        actor="robot",
    )


async def prueba_segunda_glosa_sobre_glosada_se_registra_sin_mover_el_estado() -> None:
    repositorio = _ObservacionesFalso()
    estado_cuenta = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    eventos = _RegistroEventosFalso()
    caso_uso = _registrar(repositorio, estado_cuenta, eventos)

    await caso_uso.ejecutar(_datos("OBS-01", False))
    resultado = await caso_uso.ejecutar(_datos("OBS-04", True))

    assert resultado.estado_cuenta == "GLOSADA"
    assert estado_cuenta.estados[1] == "GLOSADA"
    assert len(await repositorio.listar_por_cuenta(1)) == 2
    segundo = eventos.eventos[1]
    assert segundo.tipo_evento == "OBSERVACION_ADICIONAL"
    assert (segundo.estado_previo, segundo.estado_nuevo) == (None, None)
    assert segundo.datos["responsable_rol"] == "auditor"


async def prueba_glosa_adicional_sobre_glosada_parcial_se_registra() -> None:
    repositorio = _ObservacionesFalso()
    estado_cuenta = _EstadoCuentaFalso({1: "GLOSADA_PARCIAL"})
    eventos = _RegistroEventosFalso()

    resultado = await _registrar(repositorio, estado_cuenta, eventos).ejecutar(
        _datos("OBS-01", False)
    )

    assert resultado.estado_cuenta == "GLOSADA_PARCIAL"
    assert estado_cuenta.estados[1] == "GLOSADA_PARCIAL"


async def prueba_responder_con_otra_abierta_no_mueve_y_la_ultima_subsana() -> None:
    repositorio = _ObservacionesFalso()
    estado_cuenta = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    eventos = _RegistroEventosFalso()
    registrar = _registrar(repositorio, estado_cuenta, eventos)
    primera = (await registrar.ejecutar(_datos("OBS-01", False))).observacion_id
    segunda = (await registrar.ejecutar(_datos("OBS-04", True))).observacion_id
    responder = _responder(repositorio, estado_cuenta, eventos)

    await responder.ejecutar(primera, "Respuesta uno.", None, actor="ana.analista")
    assert estado_cuenta.estados[1] == "GLOSADA"
    assert eventos.eventos[-1].estado_nuevo is None

    await responder.ejecutar(segunda, "Respuesta dos.", None, actor="auditor.prueba")
    assert estado_cuenta.estados[1] == "SUBSANADA"
    assert eventos.eventos[-1].estado_previo == "GLOSADA"
    assert eventos.eventos[-1].estado_nuevo == "SUBSANADA"


async def prueba_glosa_parcial_sobre_subsanada_respondida_vuelve_a_subsanada() -> None:
    repositorio = _ObservacionesFalso()
    estado_cuenta = _EstadoCuentaFalso({1: "SUBSANADA"})
    eventos = _RegistroEventosFalso()

    registro = await _registrar(repositorio, estado_cuenta, eventos).ejecutar(
        _datos("OBS-04", True)
    )
    assert estado_cuenta.estados[1] == "GLOSADA"

    await _responder(repositorio, estado_cuenta, eventos).ejecutar(
        registro.observacion_id, "Codificacion corregida.", None, actor="auditor.prueba"
    )
    assert estado_cuenta.estados[1] == "SUBSANADA"
