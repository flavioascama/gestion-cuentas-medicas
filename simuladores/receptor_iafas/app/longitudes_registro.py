"""Longitud de registro esperada por tabla (prefijo de archivo), para
verificar 'que cada linea tenga la longitud declarada por su prefijo'
(Seccion 9.2).

Valores tomados de sistema/backend/configuracion/esquema_tedef/esquema_2025_10.yaml
(campo `longitud_registro` de T1, T2 y T3), extraido del Anexo 1
('Anexo-1_tedef-ipress-iafas_octubre_2025.xls') en la Fase 3. Duplicado
deliberado: Regla 0.5 prohibe que este simulador importe codigo o
configuracion de sistema/backend/. Solo T1, T2 y T3 porque es lo unico que
el backend de este prototipo genera (Seccion 1.2 del plan); un archivo con
otro prefijo valido del estandar (T4-T8) se rechaza por 'prefijo
inesperado', no porque el prefijo no exista en el estandar completo.
"""

from __future__ import annotations

LONGITUDES_REGISTRO: dict[str, int] = {
    "dfac": 242,  # T1: Cabecera del documento facturador
    "date": 410,  # T2: Caracteristicas generales de la prestacion
    "dser": 244,  # T3: Detalle de procedimientos y servicios
}
