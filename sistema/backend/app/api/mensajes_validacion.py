"""Mensajes en español para los errores de validación que levanta FastAPI."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

_MAXIMO_REPORTADOS = 3

# Etiquetas de los campos de entrada, escritas como las rotula la pantalla. Todo
# campo de varias palabras del contrato debe tener la suya (lo revisa una prueba).
_ETIQUETAS = {
    "adjunto_id": "Adjunto",
    "apellidos_asegurado": "Apellidos del asegurado",
    "area": "Área",
    "atencion_id": "Atención",
    "cantidad_venta": "Cantidad vendida",
    "clave": "Contraseña",
    "clave_actual": "Contraseña actual",
    "clave_nueva": "Contraseña nueva",
    "codigo": "Código",
    "codigo_asegurado": "Código del asegurado en la IAFAS",
    "codigo_autorizacion": "Código de acreditación",
    "codigo_cie10": "Código CIE-10",
    "codigo_elegido": "Código elegido",
    "codigo_grupo": "Código del grupo",
    "codigo_producto": "Código del producto",
    "codigo_seccion": "Código de la sección",
    "codigo_subseccion": "Código de la subsección",
    "condicion_cobertura": "Condición de cobertura",
    "contenido_base64": "Contenido del archivo",
    "contenido_s01_base64": "Contenido del archivo .S01",
    "copago_cobrado": "Copago cobrado",
    "correo_id": "Correo",
    "correo_remitente": "Remitentes autorizados",
    "cuenta_id": "Cuenta",
    "cuenta_ids": "Cuentas",
    "cuenta_medica_id": "Cuenta médica",
    "descripcion": "Descripción",
    "descripcion_correccion": "Corrección realizada",
    "descripcion_registrada": "Descripción del procedimiento",
    "detalle_campo_objetado": "Dato observado por la IAFAS",
    "diagnostico_asociado_cie10": "Diagnóstico asociado (CIE-10)",
    "diagnostico_principal_cie10": "Diagnóstico principal (CIE-10)",
    "diagnosticos_secundarios_cie10": "Diagnósticos secundarios (CIE-10)",
    "dias_plazo_comunicacion_auditoria": "Resultado de auditoría (días)",
    "dias_plazo_pago_liquidacion": "Pago de liquidación (días)",
    "dias_plazo_respuesta_observacion": "Respuesta a observaciones (días)",
    "es_parcial": "Alcance de la observación",
    "evento_id": "Evento",
    "exento_igv": "IGV",
    "fecha_alta": "Fecha de alta",
    "fecha_dispensacion": "Fecha de dispensación",
    "fecha_ingreso": "Fecha de ingreso",
    "fecha_prestacion": "Fecha de prestación",
    "guia_farmacia": "Guía de farmacia",
    "hora_prestacion": "Hora de prestación",
    "hospitalizacion": "Hospitalización",
    "iafas_codigo": "IAFAS",
    "iafas_id": "IAFAS",
    "identificacion_interna": "Identificación interna",
    "inicio_sugerencia": "Inicio de la sugerencia",
    "limite": "Límite",
    "lote_id": "Lote",
    "monto_copago_fijo": "Monto del copago",
    "monto_liquidado": "Monto que liquidó la IAFAS",
    "monto_no_cubierto": "Monto no cubierto",
    "monto_observado": "Monto observado",
    "monto_pagado": "Monto que pagó la IAFAS",
    "monto_unitario": "Monto unitario",
    "motivo_codigo": "Motivo indicado por la IAFAS",
    "naturaleza_corregida": "Corregir naturaleza",
    "nombre_archivo": "Nombre del archivo",
    "nombre_s01": "Nombre del archivo .S01",
    "nombre_usuario": "Nombre de usuario",
    "nombres_asegurado": "Nombres del asegurado",
    "numero": "Número",
    "numero_colegiatura": "Número de colegiatura",
    "numero_documento": "N.° de documento",
    "numero_documento_asegurado": "N.° de documento del asegurado",
    "numero_historia_clinica": "N.° historia clínica",
    "observacion_id": "Observación",
    "periodicidad_remision_dias": "Frecuencia de remisión (días)",
    "porcentaje_coaseguro": "Porcentaje de coaseguro",
    "posicion_aceptada": "Posición aceptada",
    "procedimiento_id": "Procedimiento",
    "procedimiento_por_codificar_id": "Procedimiento por codificar",
    "producto_id": "Producto",
    "q": "Búsqueda",
    "razon_social": "Razón social",
    "responsable_usuario_id": "Responsable",
    "respuesta_sustento": "Sustento",
    "respuesta_texto": "Respuesta a la IAFAS",
    "sesion_id": "Sesión",
    "solicitud_id": "Solicitud",
    "tipo_afiliacion": "Tipo de afiliación",
    "tipo_atencion": "Tipo de atención",
    "tipo_copago": "Tipo de copago",
    "tipo_documento": "Tipo de documento",
    "tipo_documento_asegurado": "Tipo de documento del asegurado",
    "tipo_documento_autorizacion": "Tipo de documento de autorización",
    "tipo_unidad_dispensacion": "Unidad de dispensación",
    "trabajo_id": "Operación",
    "usuario_id": "Usuario",
    "ventana_monitoreo_horas": "Monitoreo de respuestas (horas)",
    "version_id": "Versión",
    "vigente_desde": "Vigente desde",
    "vigente_hasta": "Vigente hasta",
}


def _elementos(cantidad: object) -> str:
    return f"{cantidad} elemento" if cantidad == 1 else f"{cantidad} elementos"


_POR_TIPO: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "missing": lambda _c: "falta el dato",
    "string_too_long": lambda c: f"no debe pasar de {c.get('max_length')} caracteres",
    "too_long": lambda c: f"admite como máximo {_elementos(c.get('max_length'))}",
    "too_short": lambda c: f"debe tener al menos {_elementos(c.get('min_length'))}",
    "int_parsing": lambda _c: "debe ser un número entero",
    "int_type": lambda _c: "debe ser un número entero",
    "int_from_float": lambda _c: "debe ser un número entero",
    "float_parsing": lambda _c: "debe ser un número",
    "float_type": lambda _c: "debe ser un número",
    "decimal_parsing": lambda _c: "debe ser un número",
    "decimal_type": lambda _c: "debe ser un número",
    "greater_than": lambda c: f"debe ser mayor que {c.get('gt')}",
    "greater_than_equal": lambda c: f"debe ser mayor o igual que {c.get('ge')}",
    "less_than": lambda c: f"debe ser menor que {c.get('lt')}",
    "less_than_equal": lambda c: f"debe ser menor o igual que {c.get('le')}",
    "decimal_max_places": lambda c: f"admite como máximo {c.get('decimal_places')} decimales",
    "decimal_max_digits": lambda _c: "tiene demasiadas cifras",
    "decimal_whole_digits": lambda _c: "tiene demasiadas cifras",
    "enum": lambda _c: "no es una de las opciones permitidas",
    "literal_error": lambda _c: "no es una de las opciones permitidas",
    "string_pattern_mismatch": lambda _c: "no tiene el formato esperado",
}


def _texto_del_error(tipo: str, contexto: Mapping[str, Any]) -> str:
    if tipo == "string_too_short":
        minimo = contexto.get("min_length")
        if minimo == 1:
            return "no puede quedar en blanco"
        return f"debe tener al menos {minimo} caracteres"
    if tipo.startswith("datetime"):
        return "no es una fecha y hora válidas"
    if tipo.startswith("date"):
        return "no es una fecha válida"
    if tipo.startswith("time"):
        return "no es una hora válida"
    construir = _POR_TIPO.get(tipo)
    return construir(contexto) if construir else "tiene un valor no aceptado"


def _nombre_del_dato(ubicacion: Sequence[Any]) -> str:
    nombres = [parte for parte in ubicacion[1:] if isinstance(parte, str)]
    if not nombres:
        return "Los datos enviados"
    if nombres[-1] in _ETIQUETAS:
        return _ETIQUETAS[nombres[-1]]
    texto = nombres[-1].replace("_", " ")
    return texto[:1].upper() + texto[1:]


def mensaje_validacion(errores: Sequence[Mapping[str, Any]]) -> str:
    """Resume hasta tres errores de validación como frases breves."""

    frases = [
        f"{_nombre_del_dato(error.get('loc', ()))}: "
        f"{_texto_del_error(str(error.get('type', '')), error.get('ctx') or {})}."
        for error in errores[:_MAXIMO_REPORTADOS]
    ]
    return " ".join(frases) if frases else "Los datos enviados no son válidos."
