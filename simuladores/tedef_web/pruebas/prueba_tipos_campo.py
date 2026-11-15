from __future__ import annotations

from app.tipos_campo import TipoCampo, clasificar, formato_valido, obligatoriedad_es_condicional


def prueba_clasifica_fecha_con_texto_acentuado() -> None:
    assert clasificar("C1. La fecha debe ser válida.") is TipoCampo.FECHA


def prueba_clasifica_hora_con_texto_acentuado() -> None:
    assert clasificar("C1. La hora debe ser válida.") is TipoCampo.HORA


def prueba_clasifica_monto_con_decimales() -> None:
    assert clasificar("Debe consignar un valor numérico con 2 decimales.") is TipoCampo.MONTO


def prueba_clasifica_numerico_por_rango() -> None:
    assert clasificar("Solo contiene caracteres entre el rango [0 al 9]") is TipoCampo.NUMERICO


def prueba_clasifica_monto_por_defecto_0_00_aunque_no_diga_decimales() -> None:
    # Caso real: T4 campo 11 "Cantidad de Venta del Producto" (Fase 17) --
    # el propio criterio del Anexo 1 no repite la frase "valor numerico
    # con 2 decimales" de las Tablas 1-3, solo dice "rango numerico del
    # [0 al 9]", pero su valor por defecto "'0.00'" delata que admite
    # punto decimal.
    texto = (
        "C1. El campo debe contener caracteres que corresponden al rango "
        "numerico del [0 al 9]. C2. De no corresponder se consignara "
        "'0.00'. C3. El campo debe estar alineado a la derecha."
    )
    assert clasificar(texto) is TipoCampo.MONTO


def prueba_clasifica_alfanumerico_por_defecto() -> None:
    assert clasificar("Solo debe contener uno de los valores definidos") is TipoCampo.ALFANUMERICO


def prueba_clasifica_alfanumerico_cuando_el_rango_numerico_tiene_excepcion_alfanumerica() -> None:
    # Caso real: T1 campo 8 "Numero de Documento de Pago" -- la serie
    # puede ser alfanumerica aunque otra frase del mismo criterio
    # mencione un rango [0 al 9] para el resto del valor.
    texto = (
        "los primeros cuatro caracteres correspondientes a la serie podran ser "
        "alfanumericos. El numero contiene caracteres entre [0 al 9]."
    )
    assert clasificar(texto) is TipoCampo.ALFANUMERICO


def prueba_formato_valido_fecha() -> None:
    assert formato_valido(TipoCampo.FECHA, "20260601")
    assert not formato_valido(TipoCampo.FECHA, "20261301")  # mes invalido
    assert not formato_valido(TipoCampo.FECHA, "2026060")  # longitud invalida


def prueba_formato_valido_numerico() -> None:
    assert formato_valido(TipoCampo.NUMERICO, "12345")
    assert not formato_valido(TipoCampo.NUMERICO, "12a45")


def prueba_formato_valido_alfanumerico_acepta_cualquier_cosa() -> None:
    assert formato_valido(TipoCampo.ALFANUMERICO, "ABC-123 ñ")


def prueba_formato_valido_monto_acepta_el_formato_real_con_punto_decimal() -> None:
    assert formato_valido(TipoCampo.MONTO, "0.00")
    assert formato_valido(TipoCampo.MONTO, "2046.94")
    assert formato_valido(TipoCampo.MONTO, "-15.50")
    assert not formato_valido(TipoCampo.MONTO, "204694")  # sin punto decimal
    assert not formato_valido(TipoCampo.MONTO, "2046.9")  # un solo decimal


def prueba_obligatoriedad_es_condicional_cuando_el_criterio_admite_blanco() -> None:
    assert obligatoriedad_es_condicional(
        "En el caso que el Tipo del Profesional Responsable de la Prestación es "
        "igual a '00', el campo deberá ir en blanco."
    )
    assert obligatoriedad_es_condicional("De corresponder puede ser el primer diagnóstico.")
    assert not obligatoriedad_es_condicional("El campo no debe estar en blanco o nulo.")
