"""Pruebas de cada estrategia de validacion de campo (Seccion 12.1: "Cada
estrategia de validacion, con casos validos e invalidos")."""

from __future__ import annotations

from decimal import Decimal

from app.dominio.integracion.criterios import CriterioRegla
from app.dominio.integracion.esquema import CampoEsquema
from app.dominio.integracion.estrategias import (
    FechaNoPosteriorA,
    FechaValida,
    HoraValida,
    LongitudExacta,
    MontoDosDecimales,
    ObligatorioNoVacio,
    ProductoConTolerancia,
    RucValido,
    SoloDigitos,
    SumaIgualA,
    ValorEnDominio,
)


def _campo(numero: int = 1, longitud: int = 8, obligatorio: bool = True) -> CampoEsquema:
    return CampoEsquema(
        numero=numero,
        nombre="campo_prueba",
        obligatorio=obligatorio,
        longitud=longitud,
        decimales=None,
        posicion_inicial=1,
    )


def _criterio(campo_numero: int = 1, criterio_id: str = "C1") -> CriterioRegla:
    return CriterioRegla(
        tabla="T1",
        campo_numero=campo_numero,
        campo_nombre="campo_prueba",
        criterio_id=criterio_id,
        texto_literal="texto de prueba",
        implementada=True,
        regla="prueba",
    )


def prueba_obligatorio_no_vacio_detecta_vacio() -> None:
    hallazgo = ObligatorioNoVacio().evaluar(
        tabla="T1", campo=_campo(obligatorio=True), valor="   ", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None
    assert hallazgo.severidad == "error"


def prueba_obligatorio_no_vacio_acepta_valor_presente() -> None:
    hallazgo = ObligatorioNoVacio().evaluar(
        tabla="T1", campo=_campo(obligatorio=True), valor="ABC", registro={}, criterio=_criterio()
    )
    assert hallazgo is None


def prueba_obligatorio_no_vacio_ignora_campo_opcional() -> None:
    hallazgo = ObligatorioNoVacio().evaluar(
        tabla="T1", campo=_campo(obligatorio=False), valor="", registro={}, criterio=_criterio()
    )
    assert hallazgo is None


def prueba_longitud_exacta_detecta_diferencia() -> None:
    hallazgo = LongitudExacta().evaluar(
        tabla="T1", campo=_campo(longitud=8), valor="1234", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_longitud_exacta_acepta_coincidencia() -> None:
    hallazgo = LongitudExacta().evaluar(
        tabla="T1", campo=_campo(longitud=4), valor="1234", registro={}, criterio=_criterio()
    )
    assert hallazgo is None


def prueba_monto_dos_decimales_acepta_valor_valido() -> None:
    hallazgo = MontoDosDecimales().evaluar(
        tabla="T1", campo=_campo(), valor="   1250.50", registro={}, criterio=_criterio()
    )
    assert hallazgo is None


def prueba_monto_dos_decimales_rechaza_negativo() -> None:
    hallazgo = MontoDosDecimales().evaluar(
        tabla="T1", campo=_campo(), valor="-1.00", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_monto_dos_decimales_rechaza_un_decimal() -> None:
    hallazgo = MontoDosDecimales().evaluar(
        tabla="T1", campo=_campo(), valor="1250.5", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_solo_digitos_acepta_numeros() -> None:
    assert (
        SoloDigitos().evaluar(
            tabla="T1", campo=_campo(), valor="0000123", registro={}, criterio=_criterio()
        )
        is None
    )


def prueba_solo_digitos_rechaza_letras() -> None:
    hallazgo = SoloDigitos().evaluar(
        tabla="T1", campo=_campo(), valor="12A45", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_fecha_valida_acepta_fecha_correcta() -> None:
    assert (
        FechaValida().evaluar(
            tabla="T1", campo=_campo(), valor="20260915", registro={}, criterio=_criterio()
        )
        is None
    )


def prueba_fecha_valida_rechaza_fecha_inexistente() -> None:
    hallazgo = FechaValida().evaluar(
        tabla="T1", campo=_campo(), valor="20261332", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_fecha_valida_rechaza_formato_incorrecto() -> None:
    hallazgo = FechaValida().evaluar(
        tabla="T1", campo=_campo(), valor="15-09-26", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_fecha_valida_ignora_blanco() -> None:
    assert (
        FechaValida().evaluar(
            tabla="T1", campo=_campo(), valor="        ", registro={}, criterio=_criterio()
        )
        is None
    )


def prueba_hora_valida_acepta_hora_correcta() -> None:
    assert (
        HoraValida().evaluar(
            tabla="T1", campo=_campo(), valor="235959", registro={}, criterio=_criterio()
        )
        is None
    )


def prueba_hora_valida_rechaza_hora_fuera_de_rango() -> None:
    hallazgo = HoraValida().evaluar(
        tabla="T1", campo=_campo(), valor="250000", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_ruc_valido_acepta_11_digitos() -> None:
    assert (
        RucValido().evaluar(
            tabla="T1", campo=_campo(), valor="20123456789", registro={}, criterio=_criterio()
        )
        is None
    )


def prueba_ruc_valido_rechaza_longitud_incorrecta() -> None:
    hallazgo = RucValido().evaluar(
        tabla="T1", campo=_campo(), valor="2012345678", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None


def prueba_valor_en_dominio_confirmado_rechaza_con_error() -> None:
    estrategia = ValorEnDominio(codigos_validos=frozenset({"1", "2"}), confirmado=True)
    hallazgo = estrategia.evaluar(
        tabla="T1", campo=_campo(), valor="9", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None
    assert hallazgo.severidad == "error"


def prueba_valor_en_dominio_no_confirmado_rechaza_con_advertencia() -> None:
    estrategia = ValorEnDominio(codigos_validos=frozenset({"1", "2"}), confirmado=False)
    hallazgo = estrategia.evaluar(
        tabla="T1", campo=_campo(), valor="9", registro={}, criterio=_criterio()
    )
    assert hallazgo is not None
    assert hallazgo.severidad == "advertencia"


def prueba_valor_en_dominio_acepta_codigo_valido() -> None:
    estrategia = ValorEnDominio(codigos_validos=frozenset({"1", "2"}), confirmado=True)
    assert (
        estrategia.evaluar(tabla="T1", campo=_campo(), valor="1", registro={}, criterio=_criterio())
        is None
    )


def prueba_fecha_no_posterior_a_acepta_fecha_anterior_o_igual() -> None:
    estrategia = FechaNoPosteriorA(campo_referencia=1)
    resultado = estrategia.evaluar(
        tabla="T1",
        campo=_campo(9),
        valor="20260910",
        registro={1: "20260915"},
        criterio=_criterio(9),
    )
    assert resultado is None


def prueba_fecha_no_posterior_a_rechaza_fecha_posterior() -> None:
    estrategia = FechaNoPosteriorA(campo_referencia=1)
    hallazgo = estrategia.evaluar(
        tabla="T1",
        campo=_campo(9),
        valor="20260920",
        registro={1: "20260915"},
        criterio=_criterio(9),
    )
    assert hallazgo is not None


def prueba_suma_igual_a_acepta_suma_correcta() -> None:
    estrategia = SumaIgualA(campos_sumandos=(2, 3))
    registro = {2: "10.00", 3: "5.50"}
    assert (
        estrategia.evaluar(
            tabla="T2", campo=_campo(1), valor="15.50", registro=registro, criterio=_criterio(1)
        )
        is None
    )


def prueba_suma_igual_a_rechaza_suma_incorrecta() -> None:
    estrategia = SumaIgualA(campos_sumandos=(2, 3))
    registro = {2: "10.00", 3: "5.50"}
    hallazgo = estrategia.evaluar(
        tabla="T2", campo=_campo(1), valor="99.99", registro=registro, criterio=_criterio(1)
    )
    assert hallazgo is not None


def prueba_producto_con_tolerancia_acepta_dentro_del_margen() -> None:
    estrategia = ProductoConTolerancia(campo_a=15, campo_b=16, tolerancia=Decimal("0.25"))
    registro = {15: "00003", 16: "      10.00"}
    assert (
        estrategia.evaluar(
            tabla="T3", campo=_campo(19), valor="30.20", registro=registro, criterio=_criterio(19)
        )
        is None
    )


def prueba_producto_con_tolerancia_rechaza_fuera_del_margen() -> None:
    estrategia = ProductoConTolerancia(campo_a=15, campo_b=16, tolerancia=Decimal("0.25"))
    registro = {15: "00003", 16: "      10.00"}
    hallazgo = estrategia.evaluar(
        tabla="T3", campo=_campo(19), valor="31.00", registro=registro, criterio=_criterio(19)
    )
    assert hallazgo is not None
