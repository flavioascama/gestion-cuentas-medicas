"""Traduce el escenario sintetico de un asegurado (Seccion 3.3) a lo que
las pantallas de consulta y acreditacion necesitan mostrar (Seccion 9.1:
'preexistencias, exclusiones, diagnosticos en periodo de carencia y
tiempos de espera'; 'evaluacion de beneficios... copagos fijos,
coaseguros variables')."""

from __future__ import annotations

from dataclasses import dataclass

from app.datos import Asegurado


def detalle_cobertura(asegurado: Asegurado) -> list[tuple[str, str]]:
    d = asegurado.datos
    escenario = asegurado.escenario

    if escenario == "cobertura_vigente":
        return [
            ("Plan", str(d.get("plan", "-"))),
            ("Vigente desde", str(d.get("vigente_desde", "-"))),
            ("Vigente hasta", str(d.get("vigente_hasta", "-"))),
        ]
    if escenario == "cobertura_cancelada":
        return [
            ("Fecha de cancelación", str(d.get("fecha_cancelacion", "-"))),
            ("Motivo", str(d.get("motivo", "-"))),
        ]
    if escenario == "preexistencia_declarada":
        preexistencias = d.get("preexistencias_declaradas", [])
        return [("Preexistencias declaradas", ", ".join(preexistencias) or "-")]
    if escenario == "diagnostico_en_carencia":
        carencia = d.get("diagnostico_en_carencia", {})
        return [
            ("Diagnóstico en período de carencia", str(carencia.get("descripcion", "-"))),
            ("Días restantes de carencia", str(carencia.get("dias_restantes_carencia", "-"))),
        ]
    if escenario == "copago_fijo":
        copago = d.get("copago", {})
        return [
            ("Tipo de copago", "Fijo"),
            ("Monto de copago fijo", f"S/ {copago.get('monto', 0):.2f}"),
        ]
    if escenario == "coaseguro_variable":
        copago = d.get("copago", {})
        return [
            ("Tipo de copago", "Coaseguro variable"),
            ("Porcentaje de coaseguro", f"{copago.get('porcentaje', 0)}%"),
        ]
    if escenario == "atencion_accidental":
        accidente = d.get("atencion_accidental", {})
        return [
            (
                "Declaración de siniestro registrada",
                "Sí" if accidente.get("declaracion_siniestro") else "No",
            ),
            ("Fecha del siniestro", str(accidente.get("fecha_siniestro", "-"))),
            ("Descripción", str(accidente.get("descripcion", "-"))),
        ]
    if escenario == "paciente_derivado":
        derivacion = d.get("derivacion", {})
        return [
            ("IPRESS de origen (código RENIPRESS)", str(derivacion.get("ipress_origen", "-"))),
            ("Motivo de derivación", str(derivacion.get("motivo", "-"))),
        ]
    return []


@dataclass(frozen=True, slots=True)
class CamposEstructuradosCobertura:
    """Mismos datos que `detalle_cobertura`, pero con claves fijas en vez
    de una lista posicional -- la Fase 11 los necesita para que el robot
    los pueda extraer con un selector estable (`data-testid` por campo),
    sin depender de en que posicion cae cada etiqueta segun el escenario."""

    plan: str | None
    vigente_desde: str | None
    vigente_hasta: str | None
    preexistencias: str | None


def campos_estructurados_cobertura(asegurado: Asegurado) -> CamposEstructuradosCobertura:
    d = asegurado.datos
    if asegurado.escenario == "cobertura_vigente":
        return CamposEstructuradosCobertura(
            plan=str(d.get("plan")) if d.get("plan") else None,
            vigente_desde=str(d.get("vigente_desde")) if d.get("vigente_desde") else None,
            vigente_hasta=str(d.get("vigente_hasta")) if d.get("vigente_hasta") else None,
            preexistencias=None,
        )
    if asegurado.escenario == "preexistencia_declarada":
        preexistencias = d.get("preexistencias_declaradas", [])
        return CamposEstructuradosCobertura(
            plan=None,
            vigente_desde=None,
            vigente_hasta=None,
            preexistencias=", ".join(preexistencias) if preexistencias else None,
        )
    return CamposEstructuradosCobertura(
        plan=None, vigente_desde=None, vigente_hasta=None, preexistencias=None
    )


@dataclass(frozen=True, slots=True)
class DatosCopago:
    tipo: str | None
    monto_fijo: float | None
    porcentaje_coaseguro: int | None


def datos_copago(asegurado: Asegurado) -> DatosCopago:
    copago = asegurado.datos.get("copago")
    if not copago:
        return DatosCopago(tipo=None, monto_fijo=None, porcentaje_coaseguro=None)
    if copago["tipo"] == "fijo":
        return DatosCopago(
            tipo="fijo", monto_fijo=float(copago["monto"]), porcentaje_coaseguro=None
        )
    return DatosCopago(
        tipo="coaseguro", monto_fijo=None, porcentaje_coaseguro=int(copago["porcentaje"])
    )


# Tipo de afiliacion (dominio TEDEF, Tabla 2, campo 7). El padron no lo
# trae: todos sus asegurados tienen un plan de salud privado, que en ese
# dominio es "Regular" (1). Si la semilla trae `tipo_afiliacion`, manda esa.
_TIPOS_AFILIACION = {
    "1": "Regular",
    "2": "SCTR",
    "3": "Potestativo (Independiente)",
    "4": "SCTR Independiente",
    "5": "Otros contributivos y complementario",
    "6": "SOAT",
    "7": "AFOCAT",
    "8": "SIS Subsidiado",
    "9": "Semi contributivo",
}
_TIPO_AFILIACION_POR_DEFECTO = "1"


@dataclass(frozen=True, slots=True)
class DatosAfiliado:
    """Lo que la consulta muestra del afiliado ante su IAFAS: el codigo con
    que la IAFAS lo identifica, su tipo de afiliacion y la IAFAS misma."""

    codigo_asegurado: str
    tipo_afiliacion: str
    nombre_tipo_afiliacion: str
    codigo_iafas: str
    nombre_iafas: str


def datos_afiliado(asegurado: Asegurado, nombre_iafas: str) -> DatosAfiliado:
    """El padron tampoco trae el codigo de asegurado: se deriva de forma
    estable del codigo de la IAFAS y del documento (`<iafas>-<numero>`),
    salvo que la semilla traiga `codigo_asegurado`."""

    d = asegurado.datos
    tipo = str(d.get("tipo_afiliacion") or _TIPO_AFILIACION_POR_DEFECTO)
    codigo = str(
        d.get("codigo_asegurado") or f"{asegurado.iafas_codigo}-{asegurado.numero_documento}"
    )
    return DatosAfiliado(
        codigo_asegurado=codigo,
        tipo_afiliacion=tipo,
        nombre_tipo_afiliacion=_TIPOS_AFILIACION.get(tipo, tipo),
        codigo_iafas=asegurado.iafas_codigo,
        nombre_iafas=nombre_iafas,
    )


def condicion_cobertura(asegurado: Asegurado) -> str:
    """Seccion 6.1: 'condicion de cobertura' de AcreditacionModelo (el
    backend, Fase 7) -- el texto que este simulador devuelve para ese
    campo cuando el robot de la Fase 11 lo extraiga."""

    if asegurado.estado_afiliacion == "CANCELADO":
        return "NO ACREDITABLE: afiliación cancelada"
    if asegurado.escenario == "diagnostico_en_carencia":
        return "ACREDITABLE CON RESTRICCIÓN: diagnóstico en período de carencia"
    if asegurado.escenario == "preexistencia_declarada":
        return "ACREDITABLE CON RESTRICCIÓN: preexistencia declarada"
    return "ACREDITABLE"
