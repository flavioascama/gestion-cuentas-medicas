"""Pruebas del escritor de ancho fijo (Seccion 7.3, Seccion 12.1)."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from app.dominio.integracion.esquema import CampoEsquema, TablaEsquema
from app.infraestructura.tedef.escritor_ancho_fijo import (
    ErrorEscrituraTedef,
    ensamblar_archivo,
    escribir_registro,
    formatear_alfanumerico,
    formatear_fecha,
    formatear_hora,
    formatear_monto,
    formatear_numerico_con_ceros,
    transliterar_ascii,
)


def _campo(numero: int, longitud: int, decimales: int | None = None) -> CampoEsquema:
    return CampoEsquema(
        numero=numero,
        nombre=f"campo{numero}",
        obligatorio=True,
        longitud=longitud,
        decimales=decimales,
        posicion_inicial=1,
    )


def prueba_formatear_monto_valor_normal() -> None:
    campo = _campo(1, 12, decimales=2)
    assert formatear_monto(Decimal("1250.5"), campo) == "     1250.50"


def prueba_formatear_monto_por_defecto_0_00() -> None:
    campo = _campo(1, 12, decimales=2)
    assert formatear_monto(None, campo) == "        0.00"


def prueba_formatear_monto_negativo_rechazado() -> None:
    campo = _campo(1, 12, decimales=2)
    with pytest.raises(ErrorEscrituraTedef, match="negativo"):
        formatear_monto(Decimal("-1.00"), campo)


def prueba_formatear_fecha() -> None:
    campo = _campo(1, 8)
    assert formatear_fecha(date(2026, 9, 15), campo) == "20260915"


def prueba_formatear_fecha_ausente_en_blanco() -> None:
    campo = _campo(1, 8)
    assert formatear_fecha(None, campo) == "        "


def prueba_formatear_hora() -> None:
    campo = _campo(1, 6)
    assert formatear_hora(time(8, 30, 5), campo) == "083005"


def prueba_formatear_numerico_con_ceros() -> None:
    campo = _campo(1, 7)
    assert formatear_numerico_con_ceros(123, campo) == "0000123"


def prueba_formatear_numerico_demasiado_largo_falla() -> None:
    campo = _campo(1, 3)
    with pytest.raises(ErrorEscrituraTedef):
        formatear_numerico_con_ceros(12345, campo)


def prueba_formatear_alfanumerico_alinea_izquierda() -> None:
    campo = _campo(1, 10)
    assert formatear_alfanumerico("ABC", campo) == "ABC       "


def prueba_formatear_alfanumerico_vacio_en_blanco() -> None:
    campo = _campo(1, 5)
    assert formatear_alfanumerico(None, campo) == "     "


def prueba_escribir_registro_concatena_en_orden_y_verifica_longitud() -> None:
    tabla = TablaEsquema(
        id="T1",
        nombre="prueba",
        prefijo="dfac",
        obligatoria=True,
        condicional=False,
        longitud_registro=15,
        campos=(_campo(1, 8), _campo(2, 7)),
    )
    linea = escribir_registro(tabla, {1: "20260915", 2: "0000001"})
    assert linea == "202609150000001"
    assert len(linea) == 15


def prueba_escribir_registro_longitud_de_campo_incorrecta_aborta() -> None:
    tabla = TablaEsquema(
        id="T1",
        nombre="prueba",
        prefijo="dfac",
        obligatoria=True,
        condicional=False,
        longitud_registro=15,
        campos=(_campo(1, 8), _campo(2, 7)),
    )
    with pytest.raises(ErrorEscrituraTedef, match="longitud"):
        escribir_registro(tabla, {1: "2026091", 2: "0000001"})  # campo 1 con 7, no 8


def prueba_escribir_registro_campo_faltante_aborta() -> None:
    tabla = TablaEsquema(
        id="T1",
        nombre="prueba",
        prefijo="dfac",
        obligatoria=True,
        condicional=False,
        longitud_registro=15,
        campos=(_campo(1, 8), _campo(2, 7)),
    )
    with pytest.raises(ErrorEscrituraTedef, match="Falta"):
        escribir_registro(tabla, {1: "20260915"})


def prueba_transliterar_ascii_quita_tildes() -> None:
    assert transliterar_ascii("Código IPRESS ñ") == "Codigo IPRESS n"


def prueba_ensamblar_archivo_usa_crlf_y_termina_en_crlf() -> None:
    contenido = ensamblar_archivo(["linea1", "linea2"])
    assert contenido == b"linea1\r\nlinea2\r\n"


def prueba_ensamblar_archivo_vacio() -> None:
    assert ensamblar_archivo([]) == b""
