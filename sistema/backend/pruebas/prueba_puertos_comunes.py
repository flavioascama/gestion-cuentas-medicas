"""Pruebas de app/dominio/puertos_comunes.py: control C-11 (Seccion 5.2.7
de la tesis, RNF-10), "minimizacion de datos personales en los eventos".
Verifica el rechazo por clave contra el diccionario de la Seccion 5.2.7,
en el constructor de `Evento`, antes de que un caso de uso llegue siquiera
a pedirle al puerto `RegistroEventos` que lo guarde."""

from __future__ import annotations

import pytest

from app.dominio.puertos_comunes import (
    TIPO_AGREGADO_CUENTA,
    TIPO_AGREGADO_LOTE,
    TIPO_AGREGADO_SESION_PLATAFORMA,
    TIPO_AGREGADO_SESION_USUARIO,
    ErrorEventoConDatosPersonales,
    ErrorEventoSinAgregado,
    Evento,
)


def prueba_evento_sin_datos_personales_se_construye_sin_error() -> None:
    evento = Evento(
        cuenta_medica_id=1,
        tipo_evento="CUENTA_REGISTRADA",
        actor="analista.prueba",
        estado_previo=None,
        estado_nuevo="REGISTRADA",
        datos={"iafas_id": 1},
    )
    assert evento.datos == {"iafas_id": 1}


@pytest.mark.parametrize(
    "clave",
    [
        "nombres",
        "apellidos",
        "nombres_asegurado",
        "apellidos_asegurado",
        "numero_documento",
        "numero_documento_asegurado",
        "documento_paciente",
        "numero_historia_clinica",
        "diagnostico_principal_cie10",
        "fecha_nacimiento",
        "direccion",
        "telefono",
        "correo",
        "email",
    ],
)
def prueba_evento_con_clave_personal_en_el_primer_nivel_es_rechazado(clave: str) -> None:
    with pytest.raises(ErrorEventoConDatosPersonales):
        Evento(
            cuenta_medica_id=1,
            tipo_evento="CUENTA_REGISTRADA",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo="REGISTRADA",
            datos={clave: "cualquier valor"},
        )


def prueba_evento_con_clave_personal_anidada_es_rechazado() -> None:
    with pytest.raises(ErrorEventoConDatosPersonales):
        Evento(
            cuenta_medica_id=1,
            tipo_evento="CUENTA_REGISTRADA",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo="REGISTRADA",
            datos={"detalle": {"nombres": "Elvira"}},
        )


def prueba_evento_con_clave_personal_dentro_de_una_lista_es_rechazado() -> None:
    with pytest.raises(ErrorEventoConDatosPersonales):
        Evento(
            cuenta_medica_id=1,
            tipo_evento="CUENTA_REGISTRADA",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo="REGISTRADA",
            datos={"afectados": [{"numero_documento": "12345678"}]},
        )


def prueba_evento_con_clave_personal_en_mayusculas_es_rechazado() -> None:
    """La comparacion no distingue mayusculas de minusculas: el
    diccionario de claves (Seccion 1 de GUIA_ESTILO_CODIGO.md) exige
    snake_case en minusculas, pero el rechazo no debe depender de que
    quien arma el payload lo haya respetado."""
    with pytest.raises(ErrorEventoConDatosPersonales):
        Evento(
            cuenta_medica_id=1,
            tipo_evento="CUENTA_REGISTRADA",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo="REGISTRADA",
            datos={"NOMBRES": "Elvira"},
        )


# --- Fase 24 (Seccion 6.2.2, Tabla 68): un evento pertenece a exactamente
# un agregado ------------------------------------------------------------


def prueba_evento_sin_ningun_agregado_es_rechazado() -> None:
    with pytest.raises(ErrorEventoSinAgregado):
        Evento(
            cuenta_medica_id=None,
            tipo_evento="ALGO",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo=None,
        )


def prueba_evento_con_mas_de_un_agregado_es_rechazado() -> None:
    with pytest.raises(ErrorEventoSinAgregado):
        Evento(
            cuenta_medica_id=1,
            lote_id=2,
            tipo_evento="ALGO",
            actor="analista.prueba",
            estado_previo=None,
            estado_nuevo=None,
        )


@pytest.mark.parametrize(
    ("campo", "valor", "tipo_esperado"),
    [
        ("cuenta_medica_id", 7, TIPO_AGREGADO_CUENTA),
        ("lote_id", 8, TIPO_AGREGADO_LOTE),
        ("sesion_usuario_id", 9, TIPO_AGREGADO_SESION_USUARIO),
        ("sesion_plataforma_id", 10, TIPO_AGREGADO_SESION_PLATAFORMA),
    ],
)
def prueba_evento_deriva_tipo_agregado_y_agregado_id(
    campo: str, valor: int, tipo_esperado: str
) -> None:
    argumentos: dict[str, object] = {
        "cuenta_medica_id": None,
        "tipo_evento": "ALGO",
        "actor": "analista.prueba",
        "estado_previo": None,
        "estado_nuevo": None,
        campo: valor,
    }
    evento = Evento(**argumentos)  # type: ignore[arg-type]
    assert evento.tipo_agregado == tipo_esperado
    assert evento.agregado_id == valor


def prueba_evento_con_agregado_id_centinela_cero_se_reconoce_como_dado() -> None:
    """`0 or siguiente_campo` seguiria de largo porque 0 es falsy en
    Python: `agregado_id` debe comparar con `is not None`, no con
    verdad/falsedad (pruebas_integracion/prueba_inmutabilidad_evento.py
    usa 0 como id centinela de un evento de prueba sin cuenta ni lote
    real)."""

    evento = Evento(
        cuenta_medica_id=None,
        sesion_usuario_id=0,
        tipo_evento="ALGO",
        actor="analista.prueba",
        estado_previo=None,
        estado_nuevo=None,
    )
    assert evento.tipo_agregado == TIPO_AGREGADO_SESION_USUARIO
    assert evento.agregado_id == 0
