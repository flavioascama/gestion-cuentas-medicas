"""Pruebas de la normalizacion de texto libre para CPMS (Seccion 8.2,
punto 2)."""

from __future__ import annotations

from app.dominio.cpms.normalizacion import es_codigo_candidato, normalizar


def prueba_normalizar_pasa_a_minusculas() -> None:
    assert normalizar("ANESTESIA") == "anestesia"


def prueba_normalizar_quita_tildes() -> None:
    assert normalizar("evaluación preanestésica") == "evaluacion preanestesica"


def prueba_normalizar_quita_puntuacion() -> None:
    assert normalizar("oido (externo, medio) e interno.") == "oido externo medio e interno"


def prueba_normalizar_colapsa_espacios() -> None:
    assert normalizar("anestesia   para    procedimientos") == "anestesia para procedimientos"


def prueba_normalizar_es_idempotente() -> None:
    texto = "Anestesia para procedimientos en glándulas salivales"
    assert normalizar(normalizar(texto)) == normalizar(texto)


def prueba_es_codigo_candidato_acepta_solo_digitos() -> None:
    assert es_codigo_candidato("00100") is True
    assert es_codigo_candidato("123") is True


def prueba_es_codigo_candidato_rechaza_texto() -> None:
    assert es_codigo_candidato("anestesia") is False
    assert es_codigo_candidato("") is False
    assert es_codigo_candidato("00100a") is False
