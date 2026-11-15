from __future__ import annotations

from app.nombrado import PATRON_NOMBRE_S01, PATRON_NOMBRE_TXT, nombre_archivo_s01

_NOMBRE_TXT_EJEMPLO = "dfac_20100121809_00140456_20002_1234567_201606_20130605.txt"
_NOMBRE_S01_EJEMPLO = "937_20100121809_00140456_20002_1234567_201606_20130605.S01"


def prueba_patron_txt_reconoce_el_ejemplo_del_anexo_3() -> None:
    coincidencia = PATRON_NOMBRE_TXT.match(_NOMBRE_TXT_EJEMPLO)
    assert coincidencia is not None
    componentes = coincidencia.groupdict()
    assert componentes["prefijo"] == "dfac"
    assert componentes["ruc"] == "20100121809"
    assert componentes["lote"] == "1234567"


def prueba_patron_s01_reconoce_el_ejemplo_del_anexo_3() -> None:
    assert PATRON_NOMBRE_S01.match(_NOMBRE_S01_EJEMPLO) is not None


def prueba_nombre_archivo_s01_reconstruye_el_ejemplo() -> None:
    coincidencia = PATRON_NOMBRE_TXT.match(_NOMBRE_TXT_EJEMPLO)
    assert coincidencia is not None
    assert nombre_archivo_s01(coincidencia.groupdict()) == _NOMBRE_S01_EJEMPLO


def prueba_patron_txt_rechaza_prefijo_no_activo() -> None:
    # "dden" es el prefijo de T5 (Anexo 3): T5-T8 no las genera el backend
    # ni las implementa este simulador (Fases 14 y 17).
    assert (
        PATRON_NOMBRE_TXT.match("dden_20100121809_00140456_20002_1234567_201606_20130605.txt")
        is None
    )
