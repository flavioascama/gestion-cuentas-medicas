from __future__ import annotations

from app.anexo1 import TablaAnexo1
from app.datos import IpressPropia, MaestroIafas
from app.revision_forma import revisar_forma

_RUC = "20690951848"
_IPRESS = "15995250"
_IAFAS = "99553"
_LOTE = "1234567"
_PERIODO = "201606"
_FECHA = "20130605"


def _nombre(prefijo: str) -> str:
    return f"{prefijo}_{_RUC}_{_IPRESS}_{_IAFAS}_{_LOTE}_{_PERIODO}_{_FECHA}.txt"


def _archivos_conformes(tablas_anexo1: dict[str, TablaAnexo1]) -> dict[str, bytes]:
    return {
        _nombre("dfac"): (("0" * tablas_anexo1["T1"].longitud_registro) + "\r\n").encode("ascii"),
        _nombre("date"): (("0" * tablas_anexo1["T2"].longitud_registro) + "\r\n").encode("ascii"),
        _nombre("dser"): (("0" * tablas_anexo1["T3"].longitud_registro) + "\r\n").encode("ascii"),
    }


def _codigos(maestro_iafas: tuple[MaestroIafas, ...]) -> frozenset[str]:
    return frozenset(m.codigo for m in maestro_iafas)


def prueba_conforme_cuando_todo_calza(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    resultado = revisar_forma(
        _archivos_conformes(tablas_anexo1),
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert resultado.conforme
    assert not resultado.observaciones
    assert resultado.identidad is not None
    assert resultado.identidad.numero_lote == _LOTE


def prueba_conforme_con_t4_incluida(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    archivos = _archivos_conformes(tablas_anexo1)
    archivos[_nombre("dfar")] = (("0" * tablas_anexo1["T4"].longitud_registro) + "\r\n").encode(
        "ascii"
    )
    resultado = revisar_forma(
        archivos,
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert resultado.conforme
    assert "T4" in resultado.archivos_por_tabla


def prueba_observa_tabla_faltante(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    archivos = _archivos_conformes(tablas_anexo1)
    del archivos[_nombre("dser")]
    resultado = revisar_forma(
        archivos,
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-FALT" for o in resultado.observaciones)


def prueba_observa_ipress_no_asignada(
    tablas_anexo1: dict[str, TablaAnexo1], maestro_iafas: tuple[MaestroIafas, ...]
) -> None:
    otra_ipress = IpressPropia(ruc="20999999999", codigo_ipress="99999999", razon_social="Otra")
    resultado = revisar_forma(
        _archivos_conformes(tablas_anexo1),
        tablas_anexo1,
        otra_ipress,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-IPRESS" for o in resultado.observaciones)


def prueba_observa_iafas_fuera_del_maestro(
    tablas_anexo1: dict[str, TablaAnexo1], ipress_propia: IpressPropia
) -> None:
    resultado = revisar_forma(
        _archivos_conformes(tablas_anexo1),
        tablas_anexo1,
        ipress_propia,
        frozenset(),
        ya_registrado=lambda identidad: False,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-IAFAS" for o in resultado.observaciones)


def prueba_observa_longitud_de_linea_incorrecta(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    archivos = _archivos_conformes(tablas_anexo1)
    archivos[_nombre("dfac")] = b"123\r\n"
    resultado = revisar_forma(
        archivos,
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-LONG" for o in resultado.observaciones)


def prueba_observa_lote_ya_registrado(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    resultado = revisar_forma(
        _archivos_conformes(tablas_anexo1),
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: True,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-DUP" for o in resultado.observaciones)


def prueba_observa_nombre_no_normado(
    tablas_anexo1: dict[str, TablaAnexo1],
    ipress_propia: IpressPropia,
    maestro_iafas: tuple[MaestroIafas, ...],
) -> None:
    resultado = revisar_forma(
        {"archivo_cualquiera.txt": b"contenido"},
        tablas_anexo1,
        ipress_propia,
        _codigos(maestro_iafas),
        ya_registrado=lambda identidad: False,
    )
    assert not resultado.conforme
    assert any(o.codigo_error == "SIM-NOM" for o in resultado.observaciones)
