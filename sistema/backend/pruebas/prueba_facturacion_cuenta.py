"""La cuenta pasa a FACTURADA al completarse (2026-11-19): la regla
compartida (FacturarCuentaCompleta), la emision del comprobante que la
aplica a nombre de quien lo emite y la herramienta que regulariza las
cuentas completas que quedaron REGISTRADAS."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.facturacion_cuenta import FacturarCuentaCompleta, cuenta_completa
from app.dominio.integracion.puertos_ingesta import DatosNuevaCuenta, EstadoPiezasCuenta
from app.dominio.pse.casos_uso import EmitirComprobantePago
from app.dominio.pse.puertos import ErrorFaltaParaFacturar, RequisitosComprobante
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioIngestaCuentasSql,
)
from herramientas.facturar_cuentas_completas import regularizar
from pruebas.prueba_casos_uso_ingesta import RegistroEventosFalso, RepositorioCompletitudFalso
from pruebas.prueba_casos_uso_pse import EmisorPseFalso, RepositorioComprobanteFalso
from pruebas.prueba_repositorio_ingesta_cuentas import _sembrar_iafas_e_ipress

_COMPLETA = EstadoPiezasCuenta(
    estado_cuenta="REGISTRADA",
    tiene_acreditacion=True,
    cantidad_procedimientos=1,
    tiene_comprobante=True,
)


async def prueba_factura_la_cuenta_completa_a_nombre_del_actor() -> None:
    repositorio = RepositorioCompletitudFalso(_COMPLETA)
    eventos = RegistroEventosFalso()

    movida = await FacturarCuentaCompleta(repositorio, eventos).ejecutar(7, "ana.analista")

    assert movida is True
    assert repositorio.veces_marcada_facturada == 1
    [evento] = eventos.eventos
    assert (evento.tipo_evento, evento.actor, evento.cuenta_medica_id) == (
        "CUENTA_FACTURADA",
        "ana.analista",
        7,
    )
    assert (evento.estado_previo, evento.estado_nuevo, evento.datos) == (
        "REGISTRADA",
        "FACTURADA",
        {},
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"tiene_acreditacion": False},
        {"acreditable": False},
        {"tiene_diagnostico": False},
        {"cantidad_procedimientos": 0},
        {"procedimientos_por_codificar": 1},
        {"tiene_comprobante": False},
        {"exige_carta_garantia": True},
        {"estado_cuenta": "FACTURADA"},
        {"estado_cuenta": "ANULADA"},
    ],
)
async def prueba_no_factura_si_falta_una_pieza_o_no_esta_registrada(
    cambio: dict[str, object],
) -> None:
    repositorio = RepositorioCompletitudFalso(replace(_COMPLETA, **cambio))  # type: ignore[arg-type]
    eventos = RegistroEventosFalso()

    movida = await FacturarCuentaCompleta(repositorio, eventos).ejecutar(7, "ana.analista")

    assert movida is False
    assert repositorio.veces_marcada_facturada == 0
    assert eventos.eventos == []


async def prueba_no_factura_una_cuenta_inexistente() -> None:
    repositorio = RepositorioCompletitudFalso(None)

    assert (
        await FacturarCuentaCompleta(repositorio, RegistroEventosFalso()).ejecutar(7, "a") is False
    )


def prueba_la_hospitalizacion_con_carta_esta_completa() -> None:
    con_carta = replace(_COMPLETA, exige_carta_garantia=True, tiene_carta_garantia=True)

    assert cuenta_completa(con_carta) is True


def _emitir(
    completitud: RepositorioCompletitudFalso, eventos: RegistroEventosFalso
) -> tuple[EmitirComprobantePago, RepositorioComprobanteFalso]:
    comprobantes = RepositorioComprobanteFalso()
    facturacion = FacturarCuentaCompleta(completitud, eventos)
    caso_uso = EmitirComprobantePago(comprobantes, EmisorPseFalso(), eventos, None, facturacion)
    return caso_uso, comprobantes


async def prueba_emitir_el_comprobante_factura_la_cuenta_a_nombre_de_quien_lo_emite() -> None:
    # El repositorio de completitud ve la cuenta ya con su comprobante.
    completitud = RepositorioCompletitudFalso(_COMPLETA)
    eventos = RegistroEventosFalso()
    caso_uso, _ = _emitir(completitud, eventos)

    await caso_uso.ejecutar(79, "ana.analista")

    assert [e.tipo_evento for e in eventos.eventos] == [
        "COMPROBANTE_PAGO_EMITIDO",
        "CUENTA_FACTURADA",
    ]
    assert {e.actor for e in eventos.eventos} == {"ana.analista"}
    assert completitud.veces_marcada_facturada == 1


async def prueba_un_comprobante_rechazado_no_factura() -> None:
    completitud = RepositorioCompletitudFalso(_COMPLETA)
    eventos = RegistroEventosFalso()
    caso_uso, comprobantes = _emitir(completitud, eventos)
    comprobantes.requisitos = RequisitosComprobante(
        acreditada=True, con_diagnostico=True, procedimientos=0
    )

    with pytest.raises(ErrorFaltaParaFacturar):
        await caso_uso.ejecutar(79, "ana.analista")

    assert completitud.veces_marcada_facturada == 0
    assert eventos.eventos == []


def _acreditacion(cuenta_id: int) -> AcreditacionModelo:
    return AcreditacionModelo(
        cuenta_id=cuenta_id,
        condicion_cobertura="CON_COBERTURA",
        codigo_autorizacion="AUT-1",
        tipo_documento_autorizacion="1",
        codigo_asegurado="ASE-1",
        tipo_afiliacion="1",
        instante=datetime.now(UTC),
        duracion_ms=100,
        componente_ejecutor="prueba",
    )


async def _cuenta_con_piezas(sesion: AsyncSession, iafas_id: int, comprobante: bool) -> int:
    cuenta_id = await RepositorioIngestaCuentasSql(sesion).crear_cuenta(
        DatosNuevaCuenta(
            tipo_documento_asegurado="1",
            numero_documento_asegurado="12345678",
            nombres_asegurado="Ana",
            apellidos_asegurado="Perez",
            iafas_id=iafas_id,
            fecha_prestacion=date(2026, 9, 27),
            hora_prestacion=time(9, 0, 0),
            diagnostico_principal_cie10="A09X",
        )
    )
    cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta is not None
    version = CpmsVersionModelo(etiqueta=f"v{cuenta_id}", archivos_origen=[], conteo=0)
    sesion.add(version)
    await sesion.flush()
    sesion.add_all(
        [
            _acreditacion(cuenta_id),
            ProcedimientoFacturadoModelo(
                cuenta_id=cuenta_id,
                descripcion_registrada="Consulta",
                codigo_asignado="99201",
                cpms_version_id=version.id,
                origen_codigo="sugerencia",
                cantidad=1,
                monto_unitario="50.00",
                fecha=date(2026, 9, 27),
            ),
        ]
    )
    if comprobante:
        sesion.add(
            DocumentoFacturadorModelo(
                cuenta_id=cuenta_id,
                ipress_id=cuenta.ipress_id,
                tipo_documento_pago="01",
                serie="F001",
                numero=f"{cuenta_id:08d}",
                fecha_emision=date(2026, 9, 27),
            )
        )
    await sesion.commit()
    return cuenta_id


async def prueba_la_herramienta_regulariza_una_sola_vez_a_nombre_del_sistema(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        completa = await _cuenta_con_piezas(sesion, iafas_id, comprobante=True)
        incompleta = await _cuenta_con_piezas(sesion, iafas_id, comprobante=False)
        eventos = RegistroEventosFalso()

        primera = await regularizar(sesion, eventos)
        segunda = await regularizar(sesion, eventos)

        assert (primera.revisadas, primera.facturadas) == (1, [completa])
        assert (segunda.revisadas, segunda.facturadas) == (0, [])
        assert [(e.cuenta_medica_id, e.tipo_evento, e.actor) for e in eventos.eventos] == [
            (completa, "CUENTA_FACTURADA", "sistema")
        ]
        estados = {
            cuenta_id: (await sesion.get(CuentaMedicaModelo, cuenta_id, populate_existing=True))
            for cuenta_id in (completa, incompleta)
        }
        assert {k: v.estado for k, v in estados.items() if v is not None} == {
            completa: "FACTURADA",
            incompleta: "REGISTRADA",
        }
