"""Trama TEDEF de la atencion importada (2026-11-19): tipo de atencion,
medico, diagnosticos secundarios, hospitalizacion y montos por rubro; mas
la completitud y el comprobante con procedimientos por codificar o sin
carta de garantia en una hospitalizacion."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.dominio.integracion.atencion_hospitalaria import ErrorSistemaHospitalarioNoDisponible
from app.dominio.integracion.casos_uso_ingesta import ConsultarCompletitudCuenta
from app.dominio.integracion.lote import (
    ContextoLote,
    DocumentoLote,
    PrestacionLote,
    ProcedimientoLote,
)
from app.dominio.integracion.puertos_ingesta import EstadoPiezasCuenta
from app.dominio.pse.puertos import RequisitosComprobante
from app.infraestructura.sistema_hospitalario.fuente_atenciones_http import (
    FuenteAtencionesHttp,
)
from app.infraestructura.tedef.carga_esquema import cargar_esquema
from app.infraestructura.tedef.constructor_lote import construir_t1, construir_t2, construir_t3
from app.infraestructura.tedef.escritor_ancho_fijo import escribir_registro
from app.infraestructura.tedef.montos_lote import calcular_gastos, calcular_montos_facturados
from app.infraestructura.tedef.validador_campo import validar_registro

_ESQUEMA = cargar_esquema()
_CONTEXTO = ContextoLote(
    numero_lote="0000001",
    periodo="202611",
    generado_en=datetime(2026, 11, 25, 8, 30),
    ruc_ipress="20123456789",
    codigo_ipress="12345678",
    codigo_iafas="20001",
    tasa_igv=Decimal("0.18"),
)


def _procedimiento(correlativo: int, area: str, monto: str) -> ProcedimientoLote:
    return ProcedimientoLote(
        correlativo=correlativo,
        codigo_cpms="85025",
        descripcion="procedimiento",
        fecha=date(2026, 11, 18),
        cantidad=1,
        monto_unitario=Decimal(monto),
        copago_variable=Decimal("0.00"),
        copago_fijo=Decimal("0.00"),
        area=area,
    )


_PROCEDIMIENTOS = (
    _procedimiento(1, "PROCEDIMIENTO", "80.00"),
    _procedimiento(2, "LABORATORIO", "35.00"),
    _procedimiento(3, "IMAGENES", "120.00"),
)


def _documento(tipo_atencion: str, **cambios: object) -> DocumentoLote:
    prestacion = PrestacionLote(
        codigo_prestacion_interno="CTA-000001",
        numero_historia_clinica="00045871",
        tipo_documento_paciente="1",
        numero_documento_paciente="81953443",
        codigo_asegurado="AS000001",
        tipo_afiliacion="1",
        codigo_autorizacion="AUT0000001",
        tipo_documento_autorizacion="01",
        fecha_prestacion=date(2026, 11, 18),
        hora_prestacion=time(10, 30),
        diagnostico_principal_cie10="A072",
        procedimientos=_PROCEDIMIENTOS,
        tipo_atencion=tipo_atencion,
        colegiatura_medico="045871",
        diagnosticos_secundarios_cie10=("E119", "I10X"),
    )
    return DocumentoLote(
        documento_id=1,
        cuenta_medica_id=1,
        tipo_documento_pago="01",
        serie="F001",
        numero="00000123",
        fecha_emision=date(2026, 11, 22),
        fecha_primer_envio=None,
        prestacion=replace(prestacion, **cambios),  # type: ignore[arg-type]
    )


def _errores(tabla: str, valores: dict[int, str]) -> list[str]:
    escribir_registro(_ESQUEMA[tabla], valores)  # sin error de longitud
    return [
        f"{h.campo_numero}: {h.mensaje}"
        for h in validar_registro(_ESQUEMA[tabla], valores)
        if h.severidad == "error"
    ]


_HOSPITALIZACION = {
    "carta": "CG-1",
    "fecha_ingreso_hospitalario": date(2026, 11, 18),
    "fecha_alta_hospitalaria": date(2026, 11, 21),
}


@pytest.mark.parametrize(
    ("tipo", "cobertura", "cambios"),
    [
        ("AMBULATORIA", "4", {}),
        ("EMERGENCIA", "6", {}),
        (
            "HOSPITALIZACION",
            "5",
            {k: v for k, v in _HOSPITALIZACION.items() if k != "carta"}
            | {"numero_carta_garantia": "CG-1"},
        ),
    ],
)
def prueba_la_trama_de_cada_tipo_de_atencion_pasa_el_prevalidador(
    tipo: str, cobertura: str, cambios: dict[str, object]
) -> None:
    documento = _documento(tipo, **cambios)
    t2 = construir_t2(_ESQUEMA["T2"], _CONTEXTO, documento, _PROCEDIMIENTOS)
    t1 = construir_t1(_ESQUEMA["T1"], _CONTEXTO, documento, t2)
    filas_t3 = [construir_t3(_ESQUEMA["T3"], _CONTEXTO, documento, p) for p in _PROCEDIMIENTOS]

    assert _errores("T2", t2) == []
    assert _errores("T1", t1) == []
    assert all(_errores("T3", fila) == [] for fila in filas_t3)
    assert t2[16] == cobertura
    assert (t2[19], t2[20]) == ("E119 ", "I10X ")
    assert (t2[23], t2[24]) == ("01", "045871")
    assert (filas_t3[0][11], filas_t3[0][12]) == ("01", "045871")
    assert [fila[23] for fila in filas_t3] == ["02", "04", "10"]
    if tipo == "HOSPITALIZACION":
        assert (t2[31], t2[32], t2[34]) == ("20261118", "20261121", "003")
    else:
        assert t2[31].strip() == t2[32].strip() == t2[34].strip() == ""


def prueba_la_cuenta_manual_viaja_como_antes() -> None:
    documento = _documento(
        "AMBULATORIA", colegiatura_medico=None, diagnosticos_secundarios_cie10=()
    )
    procedimientos = (replace(_PROCEDIMIENTOS[0], area="PROCEDIMIENTO"),)
    t2 = construir_t2(_ESQUEMA["T2"], _CONTEXTO, documento, procedimientos)
    t3 = construir_t3(_ESQUEMA["T3"], _CONTEXTO, documento, procedimientos[0])

    assert (t2[16], t2[23], t2[24].strip(), t2[19].strip()) == ("4", "00", "", "")
    assert (t3[11], t3[12].strip(), t3[23]) == ("00", "", "02")


def prueba_los_montos_caen_en_su_rubro_sin_cambiar_el_total() -> None:
    gastos = calcular_gastos(_PROCEDIMIENTOS, ())
    todo_como_procedimiento = calcular_gastos(
        tuple(replace(p, area="PROCEDIMIENTO") for p in _PROCEDIMIENTOS), ()
    )
    documento = _documento("AMBULATORIA")
    t2 = construir_t2(_ESQUEMA["T2"], _CONTEXTO, documento, _PROCEDIMIENTOS)

    assert (gastos.procedimientos, gastos.laboratorio, gastos.imagenes) == (
        Decimal("80.00"),
        Decimal("35.00"),
        Decimal("120.00"),
    )
    assert (t2[35].strip(), t2[38].strip(), t2[39].strip(), t2[48].strip()) == (
        "80.00",
        "35.00",
        "120.00",
        "235.00",
    )
    assert gastos.total_cubierto == todo_como_procedimiento.total_cubierto
    assert calcular_montos_facturados("01", gastos, Decimal("0.18")) == calcular_montos_facturados(
        "01", todo_como_procedimiento, Decimal("0.18")
    )


class _Completitud:
    def __init__(self, estado: EstadoPiezasCuenta) -> None:
        self.estado = estado
        self.facturada = False

    async def obtener_estado_piezas(self, cuenta_id: int) -> EstadoPiezasCuenta:
        return self.estado

    async def marcar_facturada(self, cuenta_id: int) -> None:
        self.facturada = True


_LISTA = EstadoPiezasCuenta(
    estado_cuenta="REGISTRADA",
    tiene_acreditacion=True,
    cantidad_procedimientos=1,
    tiene_comprobante=True,
)


async def _piezas(estado: EstadoPiezasCuenta) -> tuple[dict[str, tuple[bool, str | None]], bool]:
    repositorio = _Completitud(estado)
    resultado = await ConsultarCompletitudCuenta(repositorio).ejecutar(1)
    assert resultado is not None
    return {p.clave: (p.completa, p.accion) for p in resultado.piezas}, repositorio.facturada


async def prueba_completitud_con_procedimientos_por_codificar() -> None:
    piezas, facturada = await _piezas(replace(_LISTA, procedimientos_por_codificar=1))

    assert piezas["codificacion"] == (False, "codificar")
    assert set(piezas) == {
        "paciente_iafas",
        "cobertura",
        "codificacion",
        "comprobante",
        "diagnostico",
    }
    assert facturada is False


async def prueba_completitud_de_hospitalizacion_sin_carta() -> None:
    sin_carta, facturada = await _piezas(replace(_LISTA, exige_carta_garantia=True))
    con_carta, _ = await _piezas(
        replace(_LISTA, exige_carta_garantia=True, tiene_carta_garantia=True)
    )
    ambulatoria, _ = await _piezas(_LISTA)

    assert sin_carta["cobertura"] == (False, "registrar_carta_garantia")
    assert facturada is False
    assert con_carta["cobertura"] == (True, None)
    assert ambulatoria["cobertura"] == (True, None)


def prueba_comprobante_sin_carta_en_hospitalizacion_ni_procedimientos_por_codificar() -> None:
    requisitos = RequisitosComprobante(
        acreditada=True,
        con_diagnostico=True,
        procedimientos=1,
        por_codificar=2,
        falta_carta_garantia=True,
    )

    assert requisitos.faltantes() == (
        "que se codifiquen todos los procedimientos de la atención",
        "la carta de garantía de la hospitalización",
    )
    assert RequisitosComprobante(True, True, 1).faltantes() == ()


async def prueba_sistema_hospitalario_que_no_responde() -> None:
    fuente = FuenteAtencionesHttp("http://127.0.0.1:9", "clave", tiempo_espera_segundos=1)

    with pytest.raises(ErrorSistemaHospitalarioNoDisponible):
        await fuente.listar(None)
    with pytest.raises(ErrorSistemaHospitalarioNoDisponible):
        await fuente.obtener("AT-1")
