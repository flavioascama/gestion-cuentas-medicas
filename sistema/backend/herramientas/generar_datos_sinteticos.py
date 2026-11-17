"""Genera los datos sinteticos de la Seccion 3.3, deterministas mediante
una semilla fija. Ningun valor concreto corresponde a una persona o
entidad real (Regla 0.7); el FORMATO de cada dominio viene de una fuente
formal (Seccion 3.2), la fuente de cada eleccion esta comentada abajo.

Produce:
- pruebas/fixtures/maestro_iafas.csv (Seccion 3.3, 3 a 5 filas)
- pruebas/fixtures/maestro_ipress.csv (Seccion 3.3, 3 a 5 filas)
- simuladores/datos_semilla/asegurados.json (>=30, 8 escenarios de cobertura)
- pruebas/fixtures/cuentas_medicas.json (lotes pequeno/mediano/grande, con
  procedimientos tomados del catalogo CPMS real; no se inventa un codigo).
  Las primeras 4 cuentas ademas llevan un producto de farmacia tomado del
  catalogo GTIN transcrito (Fase 17): un escenario por cada letra del
  campo 7 presente en ese catalogo [M, I, B, A], la ultima con un
  escenario de producto no cubierto (Seccion 4).
- simuladores/datos_semilla/claves_iafas.json (Seccion 9.2/9.3: una
  contrasena ficticia por IAFAS, para que TEDEF Web cifre el .S01 y el
  receptor IAFAS lo descifre; el backend no lee este archivo, regla 11)

Todos incluyen una cabecera con la semilla y la fecha de generacion, y la
marca `ficticio: true` en cada registro (los .csv la llevan como columna;
los .json, como campo). Se versionan en Git (Seccion 3.3).

El escenario "diagnostico_en_carencia" queda con `codigo_cie10: null`
porque el catalogo CIE-10 no esta disponible en docs/fuentes/ (ver
docs/PENDIENTES.md). El codigo IPRESS no se verifica contra el padron
RENIPRESS real por la misma razon (tambien en PENDIENTES.md); el punto de
extension ya existe en app/dominio/integracion/valores.py.

Uso (desde sistema/backend/):
    uv run python herramientas/generar_datos_sinteticos.py
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from faker import Faker

from app.compartido.rutas import RAIZ_BACKEND, raiz_simuladores_datos_semilla
from app.dominio.integracion.valores import CodigoIafas, CodigoIpress, Ruc, sin_colision_con_padron
from herramientas.cargar_cpms import _descubrir_partes, _leer_procedimientos
from herramientas.escenarios_asegurados import datos_escenario as generar_datos_escenario
from herramientas.escenarios_asegurados import numero_documento as generar_numero_documento
from herramientas.escenarios_productos_farmacia import asignar_productos_demo

# Semilla fija arbitraria: lo unico que importa es que sea constante y este
# documentada, para que la generacion sea reproducible (Seccion 3.3).
SEMILLA = 20250601

SALIDA_MAESTRO_IAFAS = RAIZ_BACKEND / "pruebas" / "fixtures" / "maestro_iafas.csv"
SALIDA_MAESTRO_IPRESS = RAIZ_BACKEND / "pruebas" / "fixtures" / "maestro_ipress.csv"
SALIDA_ASEGURADOS = raiz_simuladores_datos_semilla() / "asegurados.json"
SALIDA_CUENTAS = RAIZ_BACKEND / "pruebas" / "fixtures" / "cuentas_medicas.json"
SALIDA_CLAVES_IAFAS = raiz_simuladores_datos_semilla() / "claves_iafas.json"
# Codigo y razon social de cada IAFAS: el receptor IAFAS presenta un portal
# por aseguradora y necesita saber como se llama cada una.
SALIDA_IAFAS_SEMILLA = raiz_simuladores_datos_semilla() / "iafas.json"

# Dominio literal del campo 9 de T2 (tipo de documento de identidad),
# transcrito de configuracion/esquema_tedef/esquema_2025_10.yaml, que a su
# vez lo tomo del Anexo 1 (Seccion 3.2: "Valores del dominio del anexo
# TEDEF" rige el tipo de documento de identidad del paciente).
TIPOS_DOCUMENTO_IDENTIDAD = ["1", "2", "3"]  # DNI, Carnet de extranjeria, Pasaporte

ESCENARIOS = [
    "cobertura_vigente",
    "cobertura_cancelada",
    "preexistencia_declarada",
    "diagnostico_en_carencia",
    "copago_fijo",
    "coaseguro_variable",
    "atencion_accidental",
    "paciente_derivado",
]
_ASEGURADOS_POR_ESCENARIO = 4  # 8 escenarios x 4 = 32, cumple el ">= 30" de la Seccion 3.3


def _cabecera(descripcion: str) -> dict[str, Any]:
    return {
        "ficticio": True,
        "semilla": SEMILLA,
        "generado_en": datetime.now(UTC).isoformat(),
        "descripcion": descripcion,
    }


# --------------------------------------------------------------------------
# Maestros (Seccion 3.3, Decision de la Fase 1 #9: 3 a 5 registros)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _FilaIafas:
    codigo: str
    razon_social: str
    periodicidad_remision_dias: int
    ventana_monitoreo_horas: int
    ficticio: bool = True


def _generar_maestro_iafas(faker: Faker) -> list[_FilaIafas]:
    codigos_usados: set[str] = set()
    filas = []
    for _ in range(4):
        while True:
            codigo = str(random.randint(0, 99999)).zfill(5)
            if codigo not in codigos_usados:
                codigos_usados.add(codigo)
                break
        CodigoIafas(codigo)  # valida formato; lanza si algo esta mal
        filas.append(
            _FilaIafas(
                codigo=codigo,
                razon_social=f"{faker.company()} IAFAS",
                periodicidad_remision_dias=random.choice([1, 7, 15, 30]),
                ventana_monitoreo_horas=random.choice([24, 48, 72]),
            )
        )
    return filas


@dataclass(frozen=True, slots=True)
class _FilaIpress:
    ruc: str
    codigo_ipress: str
    razon_social: str
    ficticio: bool = True


def _generar_codigo_ipress(codigos_usados: set[str]) -> str:
    """8 caracteres (Seccion 2.2). No se verifica contra el padron RENIPRESS
    real: no esta disponible en docs/fuentes/ (docs/PENDIENTES.md)."""

    while True:
        codigo = str(random.randint(0, 99999999)).zfill(8)
        if codigo in codigos_usados:
            continue
        CodigoIpress(codigo)  # valida formato
        if not sin_colision_con_padron(codigo, None):
            continue  # nunca ocurre mientras el padron no este disponible
        codigos_usados.add(codigo)
        return codigo


def _generar_maestro_ipress(faker: Faker) -> list[_FilaIpress]:
    codigos_usados: set[str] = set()
    filas = []
    for _ in range(4):
        ruc = Ruc("20" + str(random.randint(0, 999999999)).zfill(9))
        codigo_ipress = _generar_codigo_ipress(codigos_usados)
        filas.append(
            _FilaIpress(
                ruc=ruc.valor,
                codigo_ipress=codigo_ipress,
                razon_social=f"Clinica {faker.last_name()} S.A.C.",
            )
        )
    return filas


def _generar_claves_iafas(filas_iafas: list[_FilaIafas], faker: Faker) -> dict[str, str]:
    """Contrasena ficticia por IAFAS (Seccion 9.2, Seccion 9.3): la usan
    TEDEF Web para cifrar el .S01 con `pyzipper` y el receptor IAFAS para
    descifrarlo. Ninguna otra aplicacion la necesita (regla 11: el backend
    no lee este archivo, el .S01 es opaco para el)."""

    return {fila.codigo: faker.password(length=16, special_chars=False) for fila in filas_iafas}


def _escribir_csv_con_cabecera(ruta: Path, cabecera: dict[str, Any], filas: list[Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        archivo.write(f"# {json.dumps(cabecera, ensure_ascii=False)}\n")
        if not filas:
            return
        escritor = csv.DictWriter(archivo, fieldnames=list(asdict(filas[0]).keys()))
        escritor.writeheader()
        escritor.writerows(asdict(fila) for fila in filas)


# --------------------------------------------------------------------------
# Asegurados (Seccion 3.3, Seccion 9.1): 8 escenarios de ACREDITA SALUD
# --------------------------------------------------------------------------


def _generar_asegurados(
    faker: Faker, codigos_iafas: list[str], codigos_ipress_maestro: list[str]
) -> list[dict[str, Any]]:
    documentos_usados: set[tuple[str, str]] = set()
    asegurados = []
    for escenario in ESCENARIOS:
        for _ in range(_ASEGURADOS_POR_ESCENARIO):
            tipo_documento = random.choice(TIPOS_DOCUMENTO_IDENTIDAD)
            while True:
                numero_documento = generar_numero_documento(tipo_documento, faker)
                clave = (tipo_documento, numero_documento)
                if clave not in documentos_usados:
                    documentos_usados.add(clave)
                    break
            asegurados.append(
                {
                    "documento": {"tipo": tipo_documento, "numero": numero_documento},
                    "nombres": faker.first_name(),
                    "apellidos": f"{faker.last_name()} {faker.last_name()}",
                    "iafas_codigo": faker.random_element(codigos_iafas),
                    "escenario": escenario,
                    "ficticio": True,
                    **generar_datos_escenario(escenario, faker, codigos_ipress_maestro),
                }
            )
    return asegurados


# --------------------------------------------------------------------------
# Cuentas medicas con procedimientos (Seccion 3.3): lotes de prueba
# --------------------------------------------------------------------------

_TAMANOS_LOTE = {"pequeno": 2, "mediano": 10, "grande": 50}


def _cargar_catalogo_cpms() -> list[dict[str, Any]]:
    partes = _descubrir_partes()
    procedimientos = []
    for parte in partes:
        procedimientos.extend(_leer_procedimientos(parte))
    return procedimientos


def _generar_cuenta(
    indice: int,
    asegurados_facturables: list[dict[str, Any]],
    codigo_ipress_propio: str,
    catalogo_cpms: list[dict[str, Any]],
    faker: Faker,
) -> dict[str, Any]:
    asegurado = faker.random_element(asegurados_facturables)
    cantidad_procedimientos = random.randint(1, 4)
    procedimientos_elegidos = random.sample(catalogo_cpms, cantidad_procedimientos)
    return {
        "id_interno": f"CTA-{indice:06d}",
        "asegurado_documento": asegurado["documento"],
        "iafas_codigo": asegurado["iafas_codigo"],
        "ipress_codigo": codigo_ipress_propio,
        "fecha_prestacion": date.today().strftime("%Y%m%d"),
        "procedimientos": [
            {
                "codigo_cpms": procedimiento["codigo_procedimiento"],
                "denominacion": procedimiento["denominacion_procedimiento"],
                "cantidad": random.randint(1, 3),
                "monto_unitario": round(random.uniform(30, 500), 2),
            }
            for procedimiento in procedimientos_elegidos
        ],
        "ficticio": True,
    }


def _generar_cuentas_medicas(
    asegurados: list[dict[str, Any]], codigo_ipress_propio: str, faker: Faker
) -> dict[str, list[dict[str, Any]]]:
    asegurados_facturables = [
        asegurado for asegurado in asegurados if asegurado["estado_afiliacion"] == "ACTIVO"
    ]
    catalogo_cpms = _cargar_catalogo_cpms()

    lotes = {}
    indice = 1
    for nombre_lote, tamano in _TAMANOS_LOTE.items():
        cuentas = []
        for _ in range(tamano):
            cuentas.append(
                _generar_cuenta(
                    indice, asegurados_facturables, codigo_ipress_propio, catalogo_cpms, faker
                )
            )
            indice += 1
        lotes[nombre_lote] = cuentas
    asignar_productos_demo(lotes, faker)
    return lotes


# --------------------------------------------------------------------------


def _escribir_claves_iafas(filas_iafas: list[_FilaIafas], faker: Faker) -> None:
    claves_iafas = _generar_claves_iafas(filas_iafas, faker)
    SALIDA_CLAVES_IAFAS.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA_CLAVES_IAFAS.open("w", encoding="utf-8") as archivo:
        json.dump(
            {
                "metadatos": _cabecera(
                    "Contrasenas ficticias por IAFAS para TEDEF Web y receptor IAFAS "
                    "(Seccion 9.2/9.3)"
                )
            }
            | {"claves": claves_iafas},
            archivo,
            ensure_ascii=False,
            indent=2,
        )
    print(f"{SALIDA_CLAVES_IAFAS}: {len(claves_iafas)} claves")


def _escribir_asegurados(
    faker: Faker, codigos_iafas: list[str], codigos_ipress: list[str]
) -> list[dict[str, Any]]:
    asegurados = _generar_asegurados(faker, codigos_iafas, codigos_ipress)
    SALIDA_ASEGURADOS.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA_ASEGURADOS.open("w", encoding="utf-8") as archivo:
        json.dump(
            {"metadatos": _cabecera("Asegurados sinteticos, 8 escenarios (Seccion 3.3)")}
            | {"asegurados": asegurados},
            archivo,
            ensure_ascii=False,
            indent=2,
        )
    print(f"{SALIDA_ASEGURADOS}: {len(asegurados)} asegurados")
    return asegurados


def _escribir_cuentas(
    asegurados: list[dict[str, Any]], codigo_ipress_propio: str, faker: Faker
) -> None:
    print("Cargando catalogo CPMS desde docs/fuentes/ para las cuentas medicas...")
    lotes = _generar_cuentas_medicas(asegurados, codigo_ipress_propio, faker)
    SALIDA_CUENTAS.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA_CUENTAS.open("w", encoding="utf-8") as archivo:
        json.dump(
            {"metadatos": _cabecera("Cuentas medicas sinteticas por tamano de lote (Seccion 3.3)")}
            | {"lotes": lotes},
            archivo,
            ensure_ascii=False,
            indent=2,
        )
    for nombre_lote, cuentas in lotes.items():
        print(f"  lote {nombre_lote}: {len(cuentas)} cuentas")
    print(f"{SALIDA_CUENTAS} generado.")


def _escribir_iafas_semilla(filas_iafas: list[_FilaIafas]) -> None:
    SALIDA_IAFAS_SEMILLA.parent.mkdir(parents=True, exist_ok=True)
    contenido = {
        "metadatos": _cabecera(
            "IAFAS del maestro sintetico (codigo y razon social) para los portales "
            "por aseguradora del receptor IAFAS (Seccion 9.3)"
        ),
        "iafas": [
            {"codigo": fila.codigo, "razon_social": fila.razon_social}
            for fila in sorted(filas_iafas, key=lambda f: f.codigo)
        ],
    }
    with SALIDA_IAFAS_SEMILLA.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
    print(f"{SALIDA_IAFAS_SEMILLA}: {len(filas_iafas)} IAFAS")


def main() -> None:
    random.seed(SEMILLA)
    faker = Faker("es_ES")
    Faker.seed(SEMILLA)

    filas_iafas = _generar_maestro_iafas(faker)
    _escribir_csv_con_cabecera(
        SALIDA_MAESTRO_IAFAS, _cabecera("Maestro sintetico de IAFAS (Seccion 3.3)"), filas_iafas
    )
    print(f"{SALIDA_MAESTRO_IAFAS}: {len(filas_iafas)} filas")

    _escribir_claves_iafas(filas_iafas, faker)
    _escribir_iafas_semilla(filas_iafas)

    filas_ipress = _generar_maestro_ipress(faker)
    _escribir_csv_con_cabecera(
        SALIDA_MAESTRO_IPRESS, _cabecera("Maestro sintetico de IPRESS (Seccion 3.3)"), filas_ipress
    )
    print(f"{SALIDA_MAESTRO_IPRESS}: {len(filas_ipress)} filas")

    codigos_iafas = [fila.codigo for fila in filas_iafas]
    codigos_ipress = [fila.codigo_ipress for fila in filas_ipress]
    asegurados = _escribir_asegurados(faker, codigos_iafas, codigos_ipress)
    _escribir_cuentas(asegurados, codigos_ipress[0], faker)


if __name__ == "__main__":
    main()
