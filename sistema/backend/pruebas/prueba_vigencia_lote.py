"""Lote vigente (2026-11-19): que lo deja de ser, y que la carga al
validador y la remision a la IAFAS se rechazan sin enviar nada."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.dominio.integracion.casos_uso_validacion import SolicitarCargaEnValidador
from app.dominio.integracion.puertos import ResultadoTransmision
from app.dominio.integracion.vigencia_lote import (
    DocumentoEnLote,
    ErrorLoteDesactualizado,
    VigenciaLote,
    exigir_lote_vigente,
)
from pruebas import prueba_cargar_lote_en_validador as carga
from pruebas import prueba_casos_uso_validacion_tedef as validacion
from pruebas import prueba_remitir_lote as remision

_GENERADO = datetime(2026, 11, 6, 12, 0, 0)
_ANTES = datetime(2026, 11, 5, 9, 0, 0)
_DESPUES = datetime(2026, 11, 7, 9, 0, 0)


def _documento(identificacion: str = "CTA-1", **cambios: object) -> DocumentoEnLote:
    return DocumentoEnLote(
        cuenta_medica_id=1,
        identificacion_interna=identificacion,
        estado_cuenta=str(cambios.pop("estado_cuenta", "FACTURADA")),
        **cambios,  # type: ignore[arg-type]
    )


def _vigencia(*documentos: DocumentoEnLote) -> VigenciaLote:
    return VigenciaLote(lote_id=1, generado_en=_GENERADO, documentos=documentos)


_DESACTUALIZADO = _vigencia(_documento("CTA-1"), _documento("CTA-2", estado_cuenta="ANULADA"))


# --- definicion -------------------------------------------------------------


def prueba_lote_con_cuentas_facturadas_y_comprobantes_sin_cambios_es_vigente() -> None:
    vigencia = _vigencia(
        _documento("CTA-1"),
        # Una nota o un reemplazo anteriores al lote ya van dentro de el.
        _documento("CTA-2", nota_registrada_en=_ANTES, reemplazado_en=_ANTES),
    )
    assert vigencia.vigente
    exigir_lote_vigente(vigencia)
    exigir_lote_vigente(None)


@pytest.mark.parametrize(
    "cambio",
    [
        {"estado_cuenta": "ANULADA"},
        {"estado_cuenta": "REGISTRADA"},
        {"nota_registrada_en": _DESPUES},
        {"reemplazado_en": _DESPUES},
        {"comprobante_desfasado": True},
    ],
)
def prueba_cada_cambio_de_una_cuenta_deja_el_lote_desactualizado(cambio: dict[str, object]) -> None:
    vigencia = _vigencia(_documento("CTA-1"), _documento("CTA-2", **cambio))
    assert not vigencia.vigente
    assert vigencia.cuentas_que_cambiaron == ("CTA-2",)


def prueba_compara_fechas_con_y_sin_zona() -> None:
    vigencia = _vigencia(_documento(nota_registrada_en=_DESPUES.replace(tzinfo=UTC)))
    assert not vigencia.vigente


def prueba_el_error_nombra_las_cuentas_que_cambiaron() -> None:
    with pytest.raises(ErrorLoteDesactualizado, match="CTA-2") as error:
        exigir_lote_vigente(_DESACTUALIZADO)
    assert error.value.cuentas == ("CTA-2",)
    assert "CTA-1" not in str(error.value)


# --- carga al validador -----------------------------------------------------


async def prueba_no_se_encola_la_carga_de_un_lote_desactualizado() -> None:
    trabajos = validacion._RepositorioTrabajosFalso()
    caso_uso = SolicitarCargaEnValidador(
        repositorio=validacion._RepositorioValidacionFalso(vigencia=_DESACTUALIZADO),  # type: ignore[arg-type]
        repositorio_trabajos=trabajos,  # type: ignore[arg-type]
        reloj=validacion._RelojFijo(validacion._INSTANTE),
    )
    with pytest.raises(ErrorLoteDesactualizado):
        await caso_uso.ejecutar(lote_id=1, actor="analista")
    assert trabajos.encolados == []


async def prueba_el_robot_no_sube_un_lote_que_cambio_en_la_cola(tmp_path: Path) -> None:
    repositorio = carga._repositorio_falso(tmp_path)
    repositorio.vigencia = _DESACTUALIZADO
    validador = carga._ValidadorFalso()
    caso_uso = carga._construir(repositorio, validador, tmp_path)

    with pytest.raises(ErrorLoteDesactualizado):
        await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")
    assert validador.llamadas_cargar == 0
    assert repositorio.validaciones == []


# --- remision a la IAFAS ------------------------------------------------------


async def prueba_no_se_remite_un_lote_desactualizado(tmp_path: Path) -> None:
    caso_uso, repositorio, transmisor, eventos, trabajos = remision._construir(
        remision._lote(tmp_path), ResultadoTransmision(exitosa=True)
    )
    repositorio.vigencia = _DESACTUALIZADO

    with pytest.raises(ErrorLoteDesactualizado, match="CTA-2"):
        await caso_uso.ejecutar(lote_id=1, actor="ana.analista")
    assert transmisor.llamadas == []
    assert repositorio.remisiones_registradas == []
    assert eventos.eventos == []
    assert trabajos.trabajos_encolados == []
