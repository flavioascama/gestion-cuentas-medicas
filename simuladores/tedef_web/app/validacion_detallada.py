"""Validacion detallada (Seccion 9.2, regla 2): "implementacion propia e
independiente que lee directamente el Anexo 1... formatos por tipo de
campo, obligatoriedad, dominios enumerados, llaves entre tablas". No
reproduce los 458 criterios completos del validador oficial (Seccion 9,
ultima linea de cada simulador): cubre obligatoriedad y tipo para todos
los campos de T1-T4, mas el subconjunto de dominios de
configuracion/criterios_simulados.yaml y las llaves entre tablas
verificables directamente en el texto del Anexo 1 (T2 <= T1, T3 -> T2 y
T4 -> T2, las tres por "Correlativo de la prestacion")."""

from __future__ import annotations

from dataclasses import dataclass

from app.anexo1 import CampoAnexo1, TablaAnexo1
from app.criterios_simulados import DominioSimulado
from app.tipos_campo import clasificar, formato_valido, obligatoriedad_es_condicional

ValoresLinea = dict[int, str]


@dataclass(frozen=True, slots=True)
class ObservacionDetallada:
    tabla: str
    numero_linea: int
    campo_clave: str
    campo: str
    valor_observado: str
    codigo_error: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class _ContextoLinea:
    tabla_id: str
    numero_linea: int
    campo_clave: str


def _extraer_campos(linea: str, tabla: TablaAnexo1) -> ValoresLinea:
    return {
        campo.numero: linea[
            campo.posicion_inicial - 1 : campo.posicion_inicial - 1 + campo.longitud
        ]
        for campo in tabla.campos
    }


def _campo_clave(tabla_id: str, valores: ValoresLinea) -> str:
    if tabla_id == "T1":
        return "documento facturador"
    if tabla_id == "T2":
        return f"prestacion {valores.get(5, '').strip()}"
    if tabla_id == "T4":
        return f"prestacion {valores.get(5, '').strip()}/producto {valores.get(6, '').strip()}"
    return f"prestacion {valores.get(5, '').strip()}/servicio {valores.get(6, '').strip()}"


def _validar_campo(
    contexto: _ContextoLinea, campo: CampoAnexo1, valor: str
) -> ObservacionDetallada | None:
    if (
        campo.obligatorio
        and not valor.strip()
        and not obligatoriedad_es_condicional(campo.criterios_texto)
    ):
        return ObservacionDetallada(
            contexto.tabla_id,
            contexto.numero_linea,
            contexto.campo_clave,
            campo.nombre,
            valor,
            "SIM-OBL",
            f"El campo {campo.nombre!r} es obligatorio y esta en blanco.",
        )
    if not valor.strip():
        return None
    tipo = clasificar(campo.criterios_texto)
    if not formato_valido(tipo, valor.strip()):
        return ObservacionDetallada(
            contexto.tabla_id,
            contexto.numero_linea,
            contexto.campo_clave,
            campo.nombre,
            valor,
            "SIM-TIPO",
            f"El campo {campo.nombre!r} no tiene el formato esperado ({tipo.value}).",
        )
    return None


def _validar_dominio(
    contexto: _ContextoLinea, dominio: DominioSimulado, valores: ValoresLinea
) -> ObservacionDetallada | None:
    valor = valores.get(dominio.campo, "").strip()
    if not valor or valor in dominio.valores:
        return None
    return ObservacionDetallada(
        contexto.tabla_id,
        contexto.numero_linea,
        contexto.campo_clave,
        dominio.nombre,
        valor,
        "SIM-DOM",
        f"El campo {dominio.nombre!r} tiene el valor {valor!r}, fuera del dominio permitido "
        f"{sorted(dominio.valores)}.",
    )


def _validar_linea(
    tabla: TablaAnexo1,
    numero_linea: int,
    valores: ValoresLinea,
    dominios: tuple[DominioSimulado, ...],
) -> list[ObservacionDetallada]:
    contexto = _ContextoLinea(tabla.id, numero_linea, _campo_clave(tabla.id, valores))
    observaciones = [
        observacion
        for campo in tabla.campos
        if (observacion := _validar_campo(contexto, campo, valores[campo.numero])) is not None
    ]
    observaciones.extend(
        observacion
        for dominio in dominios
        if dominio.tabla == tabla.id
        and (observacion := _validar_dominio(contexto, dominio, valores)) is not None
    )
    return observaciones


def _validar_llaves_entre_tablas(
    valores_por_tabla: dict[str, list[ValoresLinea]],
) -> list[ObservacionDetallada]:
    observaciones = []
    t1 = valores_por_tabla.get("T1", [])
    cantidad_prestaciones = None
    if t1 and t1[0].get(11, "").strip().isdigit():
        cantidad_prestaciones = int(t1[0][11].strip())

    correlativos_t2 = set()
    for numero_linea, valores in enumerate(valores_por_tabla.get("T2", []), start=1):
        correlativo = valores.get(5, "").strip()
        correlativos_t2.add(correlativo)
        if (
            cantidad_prestaciones is not None
            and correlativo.isdigit()
            and int(correlativo) > cantidad_prestaciones
        ):
            observaciones.append(
                ObservacionDetallada(
                    "T2",
                    numero_linea,
                    f"prestacion {correlativo}",
                    "Correlativo de la prestacion",
                    correlativo,
                    "SIM-REL",
                    f"El correlativo de la prestacion ({correlativo}) supera la cantidad de "
                    f"prestaciones del documento facturador ({cantidad_prestaciones}).",
                )
            )

    observaciones.extend(
        _validar_llave_hacia_t2("T3", "servicio", valores_por_tabla, correlativos_t2)
    )
    observaciones.extend(
        _validar_llave_hacia_t2("T4", "producto", valores_por_tabla, correlativos_t2)
    )
    return observaciones


def _validar_llave_hacia_t2(
    tabla_id: str,
    etiqueta_detalle: str,
    valores_por_tabla: dict[str, list[ValoresLinea]],
    correlativos_t2: set[str],
) -> list[ObservacionDetallada]:
    observaciones = []
    for numero_linea, valores in enumerate(valores_por_tabla.get(tabla_id, []), start=1):
        correlativo = valores.get(5, "").strip()
        if correlativo not in correlativos_t2:
            detalle = valores.get(6, "").strip()
            observaciones.append(
                ObservacionDetallada(
                    tabla_id,
                    numero_linea,
                    f"prestacion {correlativo}/{etiqueta_detalle} {detalle}",
                    "Correlativo de la prestacion",
                    correlativo,
                    "SIM-REL",
                    f"La prestacion {correlativo!r} no existe en la Tabla 2.",
                )
            )
    return observaciones


def validar_detallada(
    lineas_por_tabla: dict[str, list[str]],
    tablas_anexo1: dict[str, TablaAnexo1],
    dominios: tuple[DominioSimulado, ...],
) -> list[ObservacionDetallada]:
    observaciones: list[ObservacionDetallada] = []
    valores_por_tabla: dict[str, list[ValoresLinea]] = {}

    for tabla_id, lineas in lineas_por_tabla.items():
        tabla = tablas_anexo1[tabla_id]
        valores_lineas = [_extraer_campos(linea, tabla) for linea in lineas]
        valores_por_tabla[tabla_id] = valores_lineas
        for numero_linea, valores in enumerate(valores_lineas, start=1):
            observaciones.extend(_validar_linea(tabla, numero_linea, valores, dominios))

    observaciones.extend(_validar_llaves_entre_tablas(valores_por_tabla))
    return observaciones
