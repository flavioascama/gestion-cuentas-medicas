"""Validador de consistencia entre tablas (Seccion 7.5): opera sobre TODAS
las filas de T1 a T4 de un lote ya construido, a diferencia del validador
de campo (Fase 6), que ve una fila a la vez. Fuente unica de estas
reglas: la tabla de consistencia de la hoja Estandares del Anexo 3 (ya
citada en la Fase 3 para la obligatoriedad por tabla).

Las reglas de T5 a T8 no se implementan: esas tablas no se generan en
este prototipo (Seccion 1.2) y no hay filas que consistenciar. T4 es
condicional (Seccion 8.1: solo para prestaciones con productos
registrados), asi que sus reglas toleran una lista de filas vacia -- a
diferencia de T2/T3, que siempre tienen al menos una fila.
"""

from __future__ import annotations

from app.dominio.integracion.hallazgos import Hallazgo

Fila = dict[int, str]


def _v(fila: Fila, campo: int) -> str:
    return fila[campo].strip()


def _clave_documento_t1(fila: Fila) -> tuple[str, str, str, str]:
    return (_v(fila, 5), _v(fila, 6), _v(fila, 7), _v(fila, 8))  # RUC, IPRESS, tipo, numero


def _clave_documento_t2_t3(fila: Fila) -> tuple[str, str, str, str]:
    return (_v(fila, 1), _v(fila, 2), _v(fila, 3), _v(fila, 4))


def _hallazgo(tabla: str, mensaje: str, valor: str, campo_numero: int = 0) -> Hallazgo:
    return Hallazgo(
        severidad="error",
        tabla=tabla,
        campo_numero=campo_numero,
        campo_nombre="(consistencia entre tablas)",
        criterio_id="CONSISTENCIA",
        criterio_texto="Seccion 7.5: llaves primarias y de conciliacion entre tablas.",
        valor=valor,
        mensaje=mensaje,
    )


def _validar_llave_primaria_t1(filas_t1: list[Fila]) -> list[Hallazgo]:
    """Numero de lote, IAFAS, RUC, IPRESS, tipo y numero de documento de
    pago (campos 3,4,5,6,7,8) debe ser unica en el lote."""

    hallazgos: list[Hallazgo] = []
    vistas: set[tuple[str, ...]] = set()
    for fila in filas_t1:
        clave = tuple(_v(fila, c) for c in (3, 4, 5, 6, 7, 8))
        if clave in vistas:
            hallazgos.append(
                _hallazgo("T1", f"Llave primaria de T1 duplicada: {clave}", str(clave))
            )
        vistas.add(clave)
    return hallazgos


def _validar_documentos_t1_contra_prestaciones_t2(
    filas_t1: list[Fila], filas_t2: list[Fila]
) -> list[Hallazgo]:
    """Por cada documento de T1 debe existir al menos una prestacion en
    T2, "cantidad de prestaciones" (campo 11) debe coincidir con las
    prestaciones reales, y sus correlativos deben ser consecutivos desde
    1."""

    hallazgos: list[Hallazgo] = []
    for fila_t1 in filas_t1:
        clave_doc = _clave_documento_t1(fila_t1)
        prestaciones = [f for f in filas_t2 if _clave_documento_t2_t3(f) == clave_doc]
        if not prestaciones:
            mensaje = f"Documento sin ninguna prestacion en T2: {clave_doc}"
            hallazgos.append(_hallazgo("T1", mensaje, str(clave_doc)))
            continue

        cantidad_declarada = int(_v(fila_t1, 11))
        if cantidad_declarada != len(prestaciones):
            hallazgos.append(
                _hallazgo(
                    "T1",
                    f"Cantidad de prestaciones declarada ({cantidad_declarada}) no coincide "
                    f"con las prestaciones reales en T2 ({len(prestaciones)}) para {clave_doc}.",
                    str(cantidad_declarada),
                    campo_numero=11,
                )
            )

        correlativos = sorted(int(_v(f, 5)) for f in prestaciones)
        if correlativos != list(range(1, len(prestaciones) + 1)):
            hallazgos.append(
                _hallazgo(
                    "T2",
                    f"Correlativos de prestacion no consecutivos desde 1 para {clave_doc}: "
                    f"{correlativos}.",
                    str(correlativos),
                    campo_numero=5,
                )
            )
    return hallazgos


def _validar_procedimientos_t3_contra_prestaciones_t2(
    filas_t2: list[Fila], filas_t3: list[Fila]
) -> list[Hallazgo]:
    """T3 concilia con T2 (misma llave de documento + correlativo de
    prestacion): todo procedimiento debe apuntar a una prestacion real."""

    hallazgos: list[Hallazgo] = []
    prestaciones_validas = {_clave_documento_t2_t3(f) + (_v(f, 5),) for f in filas_t2}
    for fila_t3 in filas_t3:
        clave_prestacion = _clave_documento_t2_t3(fila_t3) + (_v(fila_t3, 5),)
        if clave_prestacion not in prestaciones_validas:
            hallazgos.append(
                _hallazgo(
                    "T3",
                    f"Procedimiento sin prestacion T2 correspondiente: {clave_prestacion}.",
                    str(clave_prestacion),
                )
            )
    return hallazgos


def _validar_correlativos_t3_por_prestacion(
    filas_t2: list[Fila], filas_t3: list[Fila]
) -> list[Hallazgo]:
    """El correlativo de servicio de T3 (campo 6) se reinicia por
    prestacion y debe ser ascendente desde 1."""

    hallazgos: list[Hallazgo] = []
    for fila_t2 in filas_t2:
        clave_prestacion = _clave_documento_t2_t3(fila_t2) + (_v(fila_t2, 5),)
        procedimientos = [
            f for f in filas_t3 if _clave_documento_t2_t3(f) + (_v(f, 5),) == clave_prestacion
        ]
        correlativos = sorted(int(_v(f, 6)) for f in procedimientos)
        if correlativos != list(range(1, len(procedimientos) + 1)):
            hallazgos.append(
                _hallazgo(
                    "T3",
                    f"Correlativos de servicio no consecutivos desde 1 para la prestacion "
                    f"{clave_prestacion}: {correlativos}.",
                    str(correlativos),
                    campo_numero=6,
                )
            )
    return hallazgos


def _validar_productos_t4_contra_prestaciones_t2(
    filas_t2: list[Fila], filas_t4: list[Fila]
) -> list[Hallazgo]:
    """T4 concilia con T2 igual que T3 (misma llave de documento +
    correlativo de prestacion, Seccion 8.1: campo 5 de T4 'debe estar en
    concordancia con... la tabla 1' via la prestacion de T2)."""

    hallazgos: list[Hallazgo] = []
    prestaciones_validas = {_clave_documento_t2_t3(f) + (_v(f, 5),) for f in filas_t2}
    for fila_t4 in filas_t4:
        clave_prestacion = _clave_documento_t2_t3(fila_t4) + (_v(fila_t4, 5),)
        if clave_prestacion not in prestaciones_validas:
            hallazgos.append(
                _hallazgo(
                    "T4",
                    f"Producto de farmacia sin prestacion T2 correspondiente: {clave_prestacion}.",
                    str(clave_prestacion),
                )
            )
    return hallazgos


def _validar_correlativos_t4_por_prestacion(
    filas_t2: list[Fila], filas_t4: list[Fila]
) -> list[Hallazgo]:
    """El correlativo de producto de T4 (campo 6) se reinicia por
    prestacion y debe ser ascendente desde 1 (mismo patron que T3 campo
    6). Una prestacion sin productos no aporta filas: no es un error."""

    hallazgos: list[Hallazgo] = []
    for fila_t2 in filas_t2:
        clave_prestacion = _clave_documento_t2_t3(fila_t2) + (_v(fila_t2, 5),)
        productos = [
            f for f in filas_t4 if _clave_documento_t2_t3(f) + (_v(f, 5),) == clave_prestacion
        ]
        if not productos:
            continue
        correlativos = sorted(int(_v(f, 6)) for f in productos)
        if correlativos != list(range(1, len(productos) + 1)):
            hallazgos.append(
                _hallazgo(
                    "T4",
                    f"Correlativos de producto no consecutivos desde 1 para la prestacion "
                    f"{clave_prestacion}: {correlativos}.",
                    str(correlativos),
                    campo_numero=6,
                )
            )
    return hallazgos


def validar_consistencia(
    filas_t1: list[Fila],
    filas_t2: list[Fila],
    filas_t3: list[Fila],
    filas_t4: list[Fila],
) -> list[Hallazgo]:
    return [
        *_validar_llave_primaria_t1(filas_t1),
        *_validar_documentos_t1_contra_prestaciones_t2(filas_t1, filas_t2),
        *_validar_procedimientos_t3_contra_prestaciones_t2(filas_t2, filas_t3),
        *_validar_correlativos_t3_por_prestacion(filas_t2, filas_t3),
        *_validar_productos_t4_contra_prestaciones_t2(filas_t2, filas_t4),
        *_validar_correlativos_t4_por_prestacion(filas_t2, filas_t4),
    ]
