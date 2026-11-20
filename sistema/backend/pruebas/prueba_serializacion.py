"""Pruebas de app/api/serializacion.py (Fase 19).

Bug real encontrado al verificar la Fase 18 contra Postgres real (no
detectado por ninguna prueba anterior, todas con listas vacias):
`Respuesta(**valor.__dict__)` fallaba con `AttributeError` para
cualquier objeto de valor `@dataclass(frozen=True, slots=True)` -- un
dataclass con `slots=True` no tiene `__dict__`. Estas pruebas fijan el
reemplazo (`campos()`, basado en `dataclasses.fields()`) contra los
objetos de valor reales que lo usan, no solo con listas vacias."""

from __future__ import annotations

from datetime import datetime

from app.api.esquemas_administracion import VersionCatalogoGtinRespuesta
from app.api.esquemas_cola import DetalleTrabajoRespuesta
from app.api.esquemas_cpms import CandidatoCpmsRespuesta
from app.api.serializacion import campos
from app.dominio.cpms.puertos import VersionCpms
from app.dominio.cpms.valores import CandidatoCpms
from app.dominio.farmacia.puertos import VersionCatalogoGtin
from app.dominio.puertos_comunes import DetalleTrabajo


def prueba_campos_extrae_todos_los_campos_de_un_dataclass_con_slots() -> None:
    version = VersionCpms(
        id=1, etiqueta="2026-01-01", conteo=10, archivos_origen=[], creado_en=datetime(2026, 1, 1)
    )
    assert campos(version) == {
        "id": 1,
        "etiqueta": "2026-01-01",
        "conteo": 10,
        "archivos_origen": [],
        "creado_en": datetime(2026, 1, 1),
    }


def prueba_version_catalogo_gtin_respuesta_desde_valor_no_falla_con_datos_reales() -> None:
    valor = VersionCatalogoGtin(
        id=1, ruta_origen="catalogo_gtin.yaml", conteo=19, cargado_en=datetime(2026, 1, 1)
    )
    respuesta = VersionCatalogoGtinRespuesta.desde_valor(valor)
    assert respuesta.conteo == 19


def prueba_detalle_trabajo_respuesta_desde_valor_no_falla_con_datos_reales() -> None:
    valor = DetalleTrabajo(
        id=1,
        tipo="VERIFICAR_COBERTURA",
        carga_util={"cuenta_medica_id": 1},
        estado="COMPLETADO",
        intentos=1,
        error=None,
        creado_en=datetime(2026, 1, 1),
        actualizado_en=datetime(2026, 1, 1),
    )
    respuesta = DetalleTrabajoRespuesta.desde_valor(valor)
    assert respuesta.estado == "COMPLETADO"
    # La carga util puede traer texto sensible: no sale por la API.
    assert "carga_util" not in respuesta.model_dump()


def prueba_candidato_cpms_respuesta_desde_valor_no_falla_con_datos_reales() -> None:
    valor = CandidatoCpms(
        codigo="00100",
        denominacion="Anestesia",
        codigo_grupo="1",
        nombre_grupo="Grupo",
        codigo_seccion="10",
        nombre_seccion="Seccion",
        codigo_subseccion="100",
        nombre_subseccion="Subseccion",
        puntaje=0.9,
        posicion=1,
    )
    respuesta = CandidatoCpmsRespuesta(**campos(valor))
    assert respuesta.codigo == "00100"
