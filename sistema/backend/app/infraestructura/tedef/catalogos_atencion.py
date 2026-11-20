"""Codigos del estandar TEDEF para la atencion importada del sistema
hospitalario (2026-11-19). Ninguno se inventa: cada uno se toma del dominio
del propio campo en configuracion/reglas_tedef/dominios.yaml o de la
descripcion del campo en configuracion/esquema_tedef/esquema_2025_10.yaml
(ambos transcritos del Anexo 1)."""

from __future__ import annotations

from datetime import date

from app.dominio.integracion.atencion_hospitalaria import (
    AREA_IMAGENES,
    AREA_LABORATORIO,
    AREA_PROCEDIMIENTO,
    TIPO_AMBULATORIA,
    TIPO_EMERGENCIA,
    TIPO_HOSPITALIZACION,
)

# T2 campo 16 (Tipo de Cobertura o Tipo de Prestacion): 4 = Ambulatorio,
# 5 = Hospitalaria, 6 = Emergencia.
CODIGO_COBERTURA_POR_TIPO_ATENCION = {
    TIPO_AMBULATORIA: "4",
    TIPO_EMERGENCIA: "6",
    TIPO_HOSPITALIZACION: "5",
}
CODIGO_COBERTURA_HOSPITALARIA = "5"

# T2 campo 23 y T3 campo 11 (Tipo del Profesional Responsable): 00 =
# Profesional sin colegiatura (cuenta manual, sin medico registrado);
# 01 = Colegio Medico del Peru (el sistema hospitalario siempre manda un
# medico con su colegiatura).
PROFESIONAL_SIN_COLEGIATURA = "00"
PROFESIONAL_COLEGIO_MEDICO = "01"

# T3 campo 23 (Codigo Rubro), descripcion del campo en el Anexo 1:
# 02 Consultas/Honorarios, 04 Laboratorio, 10 Examenes auxiliares y/o
# especiales (imagenes). El 02 es el que ya viajaba para todo procedimiento.
RUBRO_POR_AREA = {
    AREA_PROCEDIMIENTO: "02",
    AREA_LABORATORIO: "04",
    AREA_IMAGENES: "10",
}

# Procedimiento confirmado a mano (sin area de origen): se clasifica por la
# subseccion del catalogo CPMS solo cuando su nombre corresponde sin duda a
# un examen auxiliar de laboratorio o de imagenes. Las secciones completas
# 1.4 (Radiologia) y 1.5 (Patologia y Laboratorio) no son inequivocas:
# incluyen radiacion en oncologia, ultrasonido terapeutico, medicina
# reproductiva y "otros procedimientos". El resto queda como procedimiento.
AREA_POR_SUBSECCION_CPMS = {
    "1.4.1": AREA_IMAGENES,  # Radiologia Diagnostica (Diagnostico por Imagenes)
    "1.4.2": AREA_IMAGENES,  # Ultrasonido Diagnostico
    "1.4.5": AREA_IMAGENES,  # Seno, Mamografia
    "1.5.1": AREA_LABORATORIO,  # Bioquimica
    "1.5.2": AREA_LABORATORIO,  # Hematologia y Coagulacion
    "1.5.3": AREA_LABORATORIO,  # Inmunologia
    "1.5.4": AREA_LABORATORIO,  # Microbiologia
}


def dias_estancia(fecha_ingreso: date, fecha_alta: date) -> int:
    """T2 campo 34: dias entre el ingreso y el alta. El Anexo 1 advierte que
    los dias facturables pueden diferir de esa resta; el sistema hospitalario
    no los envia aparte, asi que se usa la resta."""
    return (fecha_alta - fecha_ingreso).days
