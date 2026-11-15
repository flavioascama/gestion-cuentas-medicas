"""Revision de forma (Seccion 9.2, regla 1 del simulador): "patron de
nombre de los .txt del Anexo 3; presencia de las tablas obligatorias; RUC
y codigo IPRESS iguales a los de la entidad seleccionada (reproduce 'La
tabla tiene codigo de IPRESS no asignado al usuario'); codigo IAFAS
existente en el maestro sintetico; longitud de cada linea igual a la del
registro de su tabla; lote no registrado antes."

Funcion pura: no toca la base de datos. La comprobacion de "lote no
registrado antes" depende del almacenamiento, asi que quien llama pasa una
funcion callback que la resuelve (evita tener que calcular la identidad
dos veces: una para saber si ya existe, otra para revisar el resto)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.anexo1 import TablaAnexo1
from app.datos import IpressPropia
from app.nombrado import PATRON_NOMBRE_TXT, tabla_del_prefijo

_TABLAS_OBLIGATORIAS = ("T1", "T2", "T3")


@dataclass(frozen=True, slots=True)
class ObservacionForma:
    tabla: str | None
    codigo_error: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class IdentidadLote:
    ruc: str
    codigo_ipress: str
    codigo_iafas: str
    numero_lote: str
    periodo: str
    fecha: str


@dataclass(frozen=True, slots=True)
class ResultadoRevisionForma:
    conforme: bool
    identidad: IdentidadLote | None
    archivos_por_tabla: dict[str, tuple[str, bytes]]
    observaciones: tuple[ObservacionForma, ...]


def lineas_de(contenido: bytes) -> list[str] | None:
    """None si el contenido no es ASCII decodificable (mismo supuesto que
    el backend y simuladores/receptor_iafas: Anexo 3, ASCII con
    transliteracion)."""

    try:
        texto = contenido.decode("ascii")
    except UnicodeDecodeError:
        return None
    if texto.endswith("\r\n"):
        texto = texto[: -len("\r\n")]
    return texto.split("\r\n") if texto else []


def _clasificar_archivos(
    archivos: dict[str, bytes],
) -> tuple[dict[str, tuple[str, bytes]], list[dict[str, str]], list[ObservacionForma]]:
    archivos_por_tabla: dict[str, tuple[str, bytes]] = {}
    componentes_vistos: list[dict[str, str]] = []
    observaciones: list[ObservacionForma] = []
    for nombre, contenido in archivos.items():
        coincidencia = PATRON_NOMBRE_TXT.match(nombre)
        if coincidencia is None:
            observaciones.append(
                ObservacionForma(
                    None,
                    "SIM-NOM",
                    f"El nombre del archivo no cumple el patron normado: {nombre!r}",
                )
            )
            continue
        componentes = coincidencia.groupdict()
        tabla = tabla_del_prefijo(componentes["prefijo"])
        assert tabla is not None  # PATRON_NOMBRE_TXT solo matchea prefijos conocidos
        archivos_por_tabla[tabla] = (nombre, contenido)
        componentes_vistos.append(componentes)
    return archivos_por_tabla, componentes_vistos, observaciones


def _identidad_comun(componentes_vistos: list[dict[str, str]]) -> IdentidadLote | None:
    claves = {"ruc", "ipress", "iafas", "lote", "periodo", "fecha"}
    distintas = {tuple(sorted(c[k] for k in claves)) for c in componentes_vistos}
    if len(distintas) != 1:
        return None
    primero = componentes_vistos[0]
    return IdentidadLote(
        ruc=primero["ruc"],
        codigo_ipress=primero["ipress"],
        codigo_iafas=primero["iafas"],
        numero_lote=primero["lote"],
        periodo=primero["periodo"],
        fecha=primero["fecha"],
    )


def _revisar_lineas(
    archivos_por_tabla: dict[str, tuple[str, bytes]], tablas_anexo1: dict[str, TablaAnexo1]
) -> list[ObservacionForma]:
    observaciones = []
    for tabla_id, (nombre, contenido) in archivos_por_tabla.items():
        lineas = lineas_de(contenido)
        if lineas is None:
            observaciones.append(
                ObservacionForma(tabla_id, "SIM-ASCII", f"{nombre}: contenido no es ASCII valido.")
            )
            continue
        longitud_esperada = tablas_anexo1[tabla_id].longitud_registro
        for numero_linea, linea in enumerate(lineas, start=1):
            if len(linea) != longitud_esperada:
                observaciones.append(
                    ObservacionForma(
                        tabla_id,
                        "SIM-LONG",
                        f"{nombre}, linea {numero_linea}: longitud {len(linea)}, "
                        f"se esperaba {longitud_esperada}.",
                    )
                )
    return observaciones


def revisar_forma(
    archivos: dict[str, bytes],
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    codigos_iafas_validos: frozenset[str],
    ya_registrado: Callable[[IdentidadLote], bool],
) -> ResultadoRevisionForma:
    archivos_por_tabla, componentes_vistos, observaciones = _clasificar_archivos(archivos)

    faltantes = [t for t in _TABLAS_OBLIGATORIAS if t not in archivos_por_tabla]
    if faltantes:
        observaciones.append(
            ObservacionForma(None, "SIM-FALT", f"Faltan tablas obligatorias: {faltantes}")
        )

    identidad = _identidad_comun(componentes_vistos) if componentes_vistos else None
    if componentes_vistos and identidad is None:
        observaciones.append(
            ObservacionForma(
                None,
                "SIM-ID",
                "Los archivos no comparten el mismo RUC, IPRESS, IAFAS, lote, periodo y fecha.",
            )
        )
        return ResultadoRevisionForma(False, None, archivos_por_tabla, tuple(observaciones))

    if identidad is None:
        return ResultadoRevisionForma(False, None, archivos_por_tabla, tuple(observaciones))

    if identidad.ruc != ipress_propia.ruc or identidad.codigo_ipress != ipress_propia.codigo_ipress:
        observaciones.append(
            ObservacionForma(
                None, "SIM-IPRESS", "La tabla tiene codigo de IPRESS no asignado al usuario."
            )
        )

    if identidad.codigo_iafas not in codigos_iafas_validos:
        observaciones.append(
            ObservacionForma(
                None,
                "SIM-IAFAS",
                f"Codigo de IAFAS no existe en el maestro sintetico: {identidad.codigo_iafas!r}",
            )
        )

    if ya_registrado(identidad):
        observaciones.append(
            ObservacionForma(
                None, "SIM-DUP", f"El lote {identidad.numero_lote!r} ya fue registrado."
            )
        )

    observaciones.extend(_revisar_lineas(archivos_por_tabla, tablas_anexo1))

    return ResultadoRevisionForma(
        not observaciones, identidad, archivos_por_tabla, tuple(observaciones)
    )
