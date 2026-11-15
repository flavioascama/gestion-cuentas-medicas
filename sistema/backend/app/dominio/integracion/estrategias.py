"""Estrategias de validacion de campo (Seccion 5.2, patron Estrategia).

Cada estrategia valida UN registro (una fila de una tabla) a la vez, con
los valores ya como texto tal como quedarian en el archivo de ancho fijo
(Seccion 7.7, punto 2: "verificado por relectura del archivo"). Ninguna
estrategia de este modulo cruza tablas ni agrega varias filas: eso es
consistencia entre tablas (Seccion 7.5) y pertenece a la Fase 7. Aqui solo
viven las familias genericas de la Seccion 7.4 que se pueden evaluar con
una sola fila: obligatorio_no_vacio, longitud_exacta, solo_digitos,
fecha_valida, hora_valida, monto_dos_decimales, valor_en_dominio,
ruc_valido, fecha_no_posterior_a, suma_igual_a (limitada a campos de la
misma fila) y producto_con_tolerancia (idem).

Todas reciben el `registro` completo (todos los campos de esa fila, como
texto, indexados por numero de campo) aunque la mayoria solo use el
propio valor: mantiene una unica interfaz (Protocol) para el registro de
la Seccion 5.2, indexado por tabla y campo.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.dominio.integracion.criterios import CriterioRegla
from app.dominio.integracion.esquema import CampoEsquema
from app.dominio.integracion.hallazgos import Hallazgo


class EstrategiaValidacion(Protocol):
    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None: ...


def _hallazgo(
    criterio: CriterioRegla, valor: str, mensaje: str, severidad: str = "error"
) -> Hallazgo:
    return Hallazgo(
        severidad=severidad,  # type: ignore[arg-type]
        tabla=criterio.tabla,
        campo_numero=criterio.campo_numero,
        campo_nombre=criterio.campo_nombre,
        criterio_id=criterio.criterio_id,
        criterio_texto=criterio.texto_literal,
        valor=valor,
        mensaje=mensaje,
    )


class ObligatorioNoVacio:
    """Estructural: se aplica a los 104 campos de T1, T2 y T3, no depende
    de una fila de criterios.csv (Seccion 7.7, punto 5)."""

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        if campo.obligatorio and not valor.strip():
            return _hallazgo(criterio, valor, "El campo es obligatorio y está vacío.")
        return None


class LongitudExacta:
    """Estructural, igual que ObligatorioNoVacio."""

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        if len(valor) != campo.longitud:
            return _hallazgo(
                criterio,
                valor,
                f"Longitud {len(valor)}, se esperaba {campo.longitud}.",
            )
        return None


class MontoDosDecimales:
    """Estructural: se aplica quando el esquema declara decimales=2."""

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        if not valor.strip():
            return None
        try:
            monto = Decimal(valor.strip())
        except InvalidOperation:
            return _hallazgo(criterio, valor, "No es un monto numérico válido.")
        if monto.as_tuple().exponent != -2:
            return _hallazgo(criterio, valor, "El monto no tiene exactamente 2 decimales.")
        if monto < 0:
            return _hallazgo(criterio, valor, "El monto no puede ser negativo (Sección 7.3).")
        return None


class SoloDigitos:
    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        contenido = valor.strip()
        if contenido and not contenido.isdigit():
            return _hallazgo(criterio, valor, "El campo debe contener solo dígitos [0-9].")
        return None


class FechaValida:
    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        contenido = valor.strip()
        if not contenido:
            return None
        if len(contenido) != 8 or not contenido.isdigit():
            return _hallazgo(criterio, valor, "La fecha debe tener formato AAAAMMDD.")
        try:
            date(int(contenido[0:4]), int(contenido[4:6]), int(contenido[6:8]))
        except ValueError:
            return _hallazgo(criterio, valor, "La fecha no es válida.")
        return None


class HoraValida:
    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        contenido = valor.strip()
        if not contenido:
            return None
        if len(contenido) != 6 or not contenido.isdigit():
            return _hallazgo(criterio, valor, "La hora debe tener formato HHMMSS.")
        hora, minuto, segundo = int(contenido[0:2]), int(contenido[2:4]), int(contenido[4:6])
        if not (0 <= hora <= 23 and 0 <= minuto <= 59 and 0 <= segundo <= 59):
            return _hallazgo(criterio, valor, "La hora no es válida.")
        return None


class RucValido:
    """Solo longitud y composición (Decisión 4, docs/DECISIONES.md): sin
    dígito verificador, la SUNAT no publica el algoritmo de módulo 11."""

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        contenido = valor.strip()
        if not contenido:
            return None
        if len(contenido) != 11 or not contenido.isdigit():
            return _hallazgo(criterio, valor, "El RUC debe tener 11 dígitos.")
        return None


class ValorEnDominio:
    """Consulta configuracion/reglas_tedef/dominios.yaml (Seccion 7.4). Un
    dominio no confirmado produce advertencia, nunca error."""

    def __init__(self, codigos_validos: frozenset[str], confirmado: bool) -> None:
        self._codigos_validos = codigos_validos
        self._confirmado = confirmado

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        contenido = valor.strip()
        if not contenido or contenido in self._codigos_validos:
            return None
        severidad = "error" if self._confirmado else "advertencia"
        sufijo = "" if self._confirmado else " (dominio candidato, sin confirmar)"
        return _hallazgo(
            criterio,
            valor,
            f"El valor no pertenece al dominio esperado{sufijo}.",
            severidad=severidad,
        )


class FechaNoPosteriorA:
    """Compara dos campos de FECHA de la misma fila."""

    def __init__(self, campo_referencia: int) -> None:
        self._campo_referencia = campo_referencia

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        propio, referencia = valor.strip(), registro.get(self._campo_referencia, "").strip()
        if not propio or not referencia:
            return None
        if propio > referencia:  # AAAAMMDD ordena lexicograficamente como fecha
            return _hallazgo(
                criterio,
                valor,
                f"Debe ser igual o anterior al campo {self._campo_referencia}.",
            )
        return None


class SumaIgualA:
    """Suma de otros campos de LA MISMA fila (Seccion 7.5 rige las sumas
    entre filas o tablas distintas; eso es Fase 7)."""

    def __init__(self, campos_sumandos: tuple[int, ...]) -> None:
        self._campos_sumandos = campos_sumandos

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        try:
            declarado = Decimal(valor.strip())
            suma = sum(
                (Decimal(registro[c].strip()) for c in self._campos_sumandos), Decimal("0.00")
            )
        except (InvalidOperation, KeyError):
            return _hallazgo(criterio, valor, "No se pudo calcular la suma esperada.")
        if declarado != suma:
            return _hallazgo(
                criterio,
                valor,
                f"Debe ser igual a la suma de los campos {self._campos_sumandos} ({suma}).",
            )
        return None


class ProductoConTolerancia:
    """Producto de otros dos campos de la misma fila, con margen de tolerancia."""

    def __init__(self, campo_a: int, campo_b: int, tolerancia: Decimal) -> None:
        self._campo_a = campo_a
        self._campo_b = campo_b
        self._tolerancia = tolerancia

    def evaluar(
        self,
        *,
        tabla: str,
        campo: CampoEsquema,
        valor: str,
        registro: Mapping[int, str],
        criterio: CriterioRegla,
    ) -> Hallazgo | None:
        try:
            declarado = Decimal(valor.strip())
            a = Decimal(registro[self._campo_a].strip())
            b = Decimal(registro[self._campo_b].strip())
        except (InvalidOperation, KeyError):
            return _hallazgo(criterio, valor, "No se pudo calcular el producto esperado.")
        esperado = a * b
        if abs(declarado - esperado) > self._tolerancia:
            return _hallazgo(
                criterio,
                valor,
                f"Debe aproximarse al producto de los campos {self._campo_a} y "
                f"{self._campo_b} ({esperado}), tolerancia {self._tolerancia}.",
            )
        return None
