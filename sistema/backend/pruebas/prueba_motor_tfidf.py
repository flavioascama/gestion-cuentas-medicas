"""Pruebas del motor de sugerencia CPMS (Seccion 8.2, puntos 4-7) contra un
catalogo sintetico pequeño (nunca el catalogo real de 12 002 filas: eso se
verifica aparte, con herramientas/evaluar_motor_cpms.py, porque construir
el indice real en cada corrida de pytest haria la suite lenta)."""

from __future__ import annotations

from pathlib import Path

from app.dominio.cpms.normalizacion import normalizar
from app.dominio.cpms.valores import FiltrosSugerencia, ProcedimientoCpms
from app.infraestructura.cpms.configuracion_motor import ConfiguracionMotorCpms
from app.infraestructura.cpms.motor_tfidf import MotorSugerenciaCpmsTfidf

_CONFIGURACION = ConfiguracionMotorCpms(
    peso_similitud_lexica=0.7,
    peso_similitud_tokens=0.3,
    candidatos_recuperados=50,
    candidatos_devueltos=10,
    ngramas_caracteres_minimo=3,
    ngramas_caracteres_maximo=5,
    ngramas_palabras_minimo=1,
    ngramas_palabras_maximo=2,
)

_CATALOGO = (
    ProcedimientoCpms(
        codigo="00100",
        denominacion="Anestesia para procedimientos en glandulas salivales",
        codigo_grupo="1",
        nombre_grupo="Anestesia",
        codigo_seccion="10",
        nombre_seccion="Cabeza",
        codigo_subseccion="101",
        nombre_subseccion="Glandulas",
    ),
    ProcedimientoCpms(
        codigo="00120",
        denominacion="Anestesia para procedimientos en el oido externo medio e interno",
        codigo_grupo="1",
        nombre_grupo="Anestesia",
        codigo_seccion="10",
        nombre_seccion="Cabeza",
        codigo_subseccion="102",
        nombre_subseccion="Oido",
    ),
    ProcedimientoCpms(
        codigo="00104",
        denominacion="Anestesia para terapia electroconvulsiva",
        codigo_grupo="1",
        nombre_grupo="Anestesia",
        codigo_seccion="11",
        nombre_seccion="Sistema nervioso",
        codigo_subseccion="110",
        nombre_subseccion="Terapias",
    ),
    ProcedimientoCpms(
        codigo="20010",
        denominacion="Extraccion de cuerpo extrano de la cornea",
        codigo_grupo="2",
        nombre_grupo="Oftalmologia",
        codigo_seccion="20",
        nombre_seccion="Ojo",
        codigo_subseccion="200",
        nombre_subseccion="Cornea",
    ),
    ProcedimientoCpms(
        codigo="20011",
        denominacion="Reparacion de laceracion de cornea sin prolapso de tejido uveal",
        codigo_grupo="2",
        nombre_grupo="Oftalmologia",
        codigo_seccion="20",
        nombre_seccion="Ojo",
        codigo_subseccion="200",
        nombre_subseccion="Cornea",
    ),
)


def _motor() -> MotorSugerenciaCpmsTfidf:
    return MotorSugerenciaCpmsTfidf.construir(
        list(_CATALOGO),
        cpms_version_id=1,
        cpms_version_etiqueta="prueba",
        configuracion=_CONFIGURACION,
    )


def prueba_encuentra_el_exacto_en_primera_posicion() -> None:
    motor = _motor()
    consulta = normalizar("Anestesia para procedimientos en glandulas salivales")
    candidatos = motor.sugerir(consulta, FiltrosSugerencia(), 10)
    assert candidatos[0].codigo == "00100"
    assert candidatos[0].posicion == 1


def prueba_tolera_un_error_de_tipeo() -> None:
    motor = _motor()
    consulta = normalizar("anestesia glandulas salibales")  # "salibales" con error
    candidatos = motor.sugerir(consulta, FiltrosSugerencia(), 10)
    codigos = [c.codigo for c in candidatos]
    assert "00100" in codigos


def prueba_texto_no_relacionado_no_devuelve_el_codigo_incorrecto_primero() -> None:
    motor = _motor()
    consulta = normalizar("extraccion cuerpo extrano cornea")
    candidatos = motor.sugerir(consulta, FiltrosSugerencia(), 10)
    assert candidatos[0].codigo == "20010"


def prueba_filtra_por_grupo() -> None:
    motor = _motor()
    consulta = normalizar("cornea")
    candidatos = motor.sugerir(consulta, FiltrosSugerencia(codigo_grupo="1"), 10)
    # Ningun procedimiento del grupo 1 (Anestesia) menciona "cornea", pero
    # el filtro debe restringir la busqueda a ese grupo igual, sin colarse
    # candidatos del grupo 2 aunque tengan mejor puntaje lexico.
    assert all(c.codigo_grupo == "1" for c in candidatos)


def prueba_filtro_sin_coincidencias_devuelve_vacio() -> None:
    motor = _motor()
    candidatos = motor.sugerir(
        normalizar("cualquier cosa"), FiltrosSugerencia(codigo_grupo="9"), 10
    )
    assert candidatos == ()


def prueba_respeta_el_maximo_de_candidatos_devueltos() -> None:
    motor = _motor()
    candidatos = motor.sugerir(normalizar("anestesia"), FiltrosSugerencia(), 2)
    assert len(candidatos) <= 2


def prueba_posiciones_son_consecutivas_desde_uno() -> None:
    motor = _motor()
    candidatos = motor.sugerir(normalizar("anestesia"), FiltrosSugerencia(), 10)
    assert [c.posicion for c in candidatos] == list(range(1, len(candidatos) + 1))


def prueba_guardar_y_cargar_el_indice_es_equivalente(tmp_path: Path) -> None:
    motor = _motor()
    ruta = tmp_path / "indice.joblib"
    motor.guardar(ruta)

    motor_cargado = MotorSugerenciaCpmsTfidf.cargar(ruta, _CONFIGURACION)
    assert motor_cargado is not None
    assert motor_cargado.cpms_version_id == motor.cpms_version_id

    consulta = normalizar("Anestesia para procedimientos en glandulas salivales")
    candidatos_originales = motor.sugerir(consulta, FiltrosSugerencia(), 10)
    candidatos_cargados = motor_cargado.sugerir(consulta, FiltrosSugerencia(), 10)
    assert candidatos_originales == candidatos_cargados


def prueba_cargar_devuelve_none_si_no_existe_el_archivo(tmp_path: Path) -> None:
    motor = MotorSugerenciaCpmsTfidf.cargar(tmp_path / "no_existe.joblib", _CONFIGURACION)
    assert motor is None
