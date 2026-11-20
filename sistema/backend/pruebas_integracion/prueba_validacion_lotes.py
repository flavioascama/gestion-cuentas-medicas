"""Escenarios 5, 6, 7 y 8 de la Seccion 14.2 del plan v3 (Integracion,
stack completo con los tres simuladores): Prevalidacion con error,
Revision de forma observada, Validacion detallada observada, Lote
conforme.

Requiere el stack completo levantado -- postgres, backend, trabajador,
tedef-web (con SIMULADOR_MODO_PRUEBA=true) -- y corre aparte de la suite
rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_validacion_lotes.py -q

Las cuatro funciones dependen del estado que deja la anterior (la sesion
asistida de tedef_web que activa la primera que la necesita se reutiliza
en las siguientes, Seccion 8.5) y por eso deben correr en el orden en que
estan escritas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, IpressModelo
from pruebas_integracion.apoyo_estados import liberar_cuenta_de_lotes_en_curso
from pruebas_integracion.conftest import esperar_hasta
from pruebas_integracion.prueba_sesion_asistida_y_cobertura import _TokenParaRol

_PLATAFORMA = "tedef_web"
_URL_TEDEF_WEB = "http://tedef-web:8000"
_TIMEOUT_INGRESO_SEGUNDOS = 30.0
_TIMEOUT_VALIDACION_SEGUNDOS = 60.0

# Cuentas FACTURADA dedicadas, una por escenario, para no competir por la
# misma fila con otro archivo de pruebas_integracion ni entre si.
_CUENTA_PREVALIDACION_CON_ERROR = 40
_CUENTA_FORMA_OBSERVADA = 41
_CUENTA_DETALLADA_OBSERVADA = 42
_CUENTA_CONFORME = 43


async def _texto_captcha_vigente_tedef_web() -> str:
    async with httpx.AsyncClient(base_url=_URL_TEDEF_WEB, timeout=5.0) as cliente:
        respuesta = await cliente.get("/admin/captcha")
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.text


async def _asegurar_sesion_tedef_web_activa(
    sesion: AsyncSession, cliente: AsyncClient, token: str
) -> None:
    """Escenarios 6 a 8: los tres dependen de una sesion asistida ACTIVA
    de tedef_web (Seccion 8.5), reutilizable entre ellos -- solo la crea
    si todavia no hay una vigente, igual que el propio
    SolicitarSesionPlataforma (idempotente)."""

    respuesta = await cliente.post(
        f"/plataformas/{_PLATAFORMA}/sesion", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text
    sesion_id = int(respuesta.json()["sesion_id"])

    async def _sesion_lista() -> str | None:
        listado = await cliente.get(
            "/plataformas/sesiones",
            params={"plataforma": _PLATAFORMA},
            headers={"Authorization": f"Bearer {token}"},
        )
        (fila,) = (f for f in listado.json() if f["id"] == sesion_id)
        return fila["estado"] if fila["estado"] in ("ESPERANDO_CAPTCHA", "ACTIVA") else None

    estado = await esperar_hasta(_sesion_lista, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)
    if estado == "ACTIVA":
        return  # idempotente: ya habia una sesion vigente, no hizo falta CAPTCHA.

    texto = await _texto_captcha_vigente_tedef_web()
    respuesta_captcha = await cliente.post(
        f"/plataformas/sesiones/{sesion_id}/captcha",
        json={"respuesta": texto},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta_captcha.status_code == 204, respuesta_captcha.text

    async def _esta_activa() -> bool:
        listado = await cliente.get(
            "/plataformas/sesiones",
            params={"plataforma": _PLATAFORMA},
            headers={"Authorization": f"Bearer {token}"},
        )
        (fila,) = (f for f in listado.json() if f["id"] == sesion_id)
        return bool(fila["estado"] == "ACTIVA")

    await esperar_hasta(_esta_activa, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)


@dataclass(frozen=True, slots=True)
class _ResultadoLote:
    conforme: bool
    lote_id: int | None
    hallazgos: list[dict[str, Any]]
    cuerpo_completo: dict[str, Any]


async def _generar_lote(
    cliente: AsyncClient, token: str, iafas_id: int, cuenta_id: int, periodo: str = "202609"
) -> _ResultadoLote:
    respuesta = await cliente.post(
        "/lotes",
        json={"iafas_id": iafas_id, "periodo": periodo, "cuenta_ids": [cuenta_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    return _ResultadoLote(
        conforme=cuerpo["conforme"],
        lote_id=cuerpo["lote_id"],
        hallazgos=cuerpo["hallazgos"],
        cuerpo_completo=cuerpo,
    )


async def _cargar_en_validador(cliente: AsyncClient, token: str, lote_id: int) -> None:
    respuesta = await cliente.post(
        f"/lotes/{lote_id}/carga-validador", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text


async def _estado_lote(cliente: AsyncClient, token: str, lote_id: int) -> str:
    respuesta = await cliente.get(f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200, respuesta.text
    return str(respuesta.json()["estado"])


async def _validacion_oficial(
    cliente: AsyncClient, token: str, lote_id: int
) -> list[dict[str, Any]]:
    respuesta = await cliente.get(
        f"/lotes/{lote_id}/validacion-oficial", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()  # type: ignore[no-any-return]


async def _iafas_de_cuenta(sesion: AsyncSession, cuenta_id: int) -> int:
    cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta is not None, f"No existe la cuenta sintetica {cuenta_id}."
    return cuenta.iafas_id


async def prueba_5_prevalidacion_con_error_no_genera_lote(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Prevalidacion con error": no se genera lote; informe
    con tabla, campo y criterio literal. `diagnostico_principal_cie10`
    en NULL viola la obligatoriedad estructural del campo 18 de T2
    (Seccion 7.1) sin lanzar ninguna excepcion no controlada (a
    diferencia de un valor no numerico en un campo que el escritor de
    ancho fijo formatea como numero, que aborta con un error de
    servidor en vez de un hallazgo)."""

    token = await token_para_rol(NombreRol.ANALISTA)
    iafas_id = await _iafas_de_cuenta(sesion, _CUENTA_PREVALIDACION_CON_ERROR)

    cuenta = await sesion.get(CuentaMedicaModelo, _CUENTA_PREVALIDACION_CON_ERROR)
    assert cuenta is not None
    diagnostico_original = cuenta.diagnostico_principal_cie10
    cuenta.diagnostico_principal_cie10 = None
    await sesion.commit()
    try:
        resultado = await _generar_lote(cliente, token, iafas_id, _CUENTA_PREVALIDACION_CON_ERROR)
    finally:
        cuenta_restaurar = await sesion.get(CuentaMedicaModelo, _CUENTA_PREVALIDACION_CON_ERROR)
        assert cuenta_restaurar is not None
        cuenta_restaurar.diagnostico_principal_cie10 = diagnostico_original
        await sesion.commit()

    assert resultado.conforme is False
    assert resultado.lote_id is None
    assert resultado.cuerpo_completo["rutas_archivos"] is None
    assert len(resultado.hallazgos) >= 1
    hallazgo = resultado.hallazgos[0]
    assert hallazgo["tabla"] == "T2"
    assert hallazgo["campo_numero"] == 18
    assert hallazgo["criterio_texto"], "El informe debe traer el criterio literal, no solo un id."
    assert hallazgo["mensaje"]


async def prueba_6_revision_de_forma_observada_codigo_ipress_ajeno(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Revision de forma observada": codigo IPRESS ajeno a la
    entidad -> lote OBSERVADO_VALIDADOR con el reporte registrado
    (SIM-IPRESS, simuladores/tedef_web/app/revision_forma.py).

    Solo existe una fila en `ipress` en todo el sistema (Seccion 6.1: una
    sola IPRESS, no una plataforma multi-tenant) y `GenerarLote` toma el
    RUC/codigo de esa fila para T1 (`obtener_ipress_propia`, sin importar
    que cuenta se facture) -- por eso se corrompe esa unica fila mientras
    dura todo el escenario, no solo mientras se genera: el nombre real
    del archivo .txt en disco (Seccion 2.2 del plan) tambien lleva ese
    RUC/codigo, y `CargarLoteEnValidador` (el trabajador, asincrono)
    reconstruye ese mismo nombre esperado leyendo la IPRESS otra vez en
    el momento en que de verdad lee el archivo -- si se restaura antes de
    que el trabajador llegue a ese punto, el nombre que reconstruye ya no
    coincide con el que quedo escrito en disco ("No such file or
    directory"). Se restaura recien cuando el lote ya no esta GENERADO."""

    token = await token_para_rol(NombreRol.ANALISTA)
    iafas_id = await _iafas_de_cuenta(sesion, _CUENTA_FORMA_OBSERVADA)

    ipress = (await sesion.execute(sa.select(IpressModelo).limit(1))).scalar_one()
    ruc_original, codigo_original = ipress.ruc, ipress.codigo_ipress
    ipress.ruc, ipress.codigo_ipress = "10000000001", "99999999"
    await sesion.commit()
    try:
        await liberar_cuenta_de_lotes_en_curso(sesion, _CUENTA_FORMA_OBSERVADA)
        resultado = await _generar_lote(cliente, token, iafas_id, _CUENTA_FORMA_OBSERVADA)
        assert resultado.conforme is True, resultado.cuerpo_completo
        lote_id = resultado.lote_id
        assert lote_id is not None

        await _asegurar_sesion_tedef_web_activa(sesion, cliente, token)
        await _cargar_en_validador(cliente, token, lote_id)

        async def _lote_ya_no_generado() -> bool:
            estado = await _estado_lote(cliente, token, lote_id)
            return estado != "GENERADO"

        await esperar_hasta(
            _lote_ya_no_generado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS
        )
    finally:
        ipress_restaurar = (await sesion.execute(sa.select(IpressModelo).limit(1))).scalar_one()
        ipress_restaurar.ruc, ipress_restaurar.codigo_ipress = ruc_original, codigo_original
        await sesion.commit()

    async def _lote_observado() -> bool:
        estado = await _estado_lote(cliente, token, lote_id)
        return bool(estado == "OBSERVADO_VALIDADOR")

    await esperar_hasta(_lote_observado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS)

    resultados = await _validacion_oficial(cliente, token, lote_id)
    forma = next(r for r in resultados if r["etapa"] == "FORMA")
    assert forma["resultado"] == "OBSERVADO"
    codigos_error = [o["codigo_error"] for o in forma["observaciones"]]
    assert "SIM-IPRESS" in codigos_error, codigos_error


async def prueba_7_validacion_detallada_observada_forzada(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Validacion detallada observada": error forzado por la
    ruta de administracion del simulador; observaciones registradas por
    linea y campo (`POST /admin/falla modo=forzar_observaciones`,
    simuladores/tedef_web, Seccion 9.2)."""

    token = await token_para_rol(NombreRol.ANALISTA)
    iafas_id = await _iafas_de_cuenta(sesion, _CUENTA_DETALLADA_OBSERVADA)
    await liberar_cuenta_de_lotes_en_curso(sesion, _CUENTA_DETALLADA_OBSERVADA)
    resultado = await _generar_lote(cliente, token, iafas_id, _CUENTA_DETALLADA_OBSERVADA)
    assert resultado.conforme is True, resultado.cuerpo_completo
    lote_id = resultado.lote_id
    assert lote_id is not None

    await _asegurar_sesion_tedef_web_activa(sesion, cliente, token)

    async with httpx.AsyncClient(base_url=_URL_TEDEF_WEB, timeout=5.0) as cliente_simulador:
        activar = await cliente_simulador.post(
            "/admin/falla", data={"modo": "forzar_observaciones"}
        )
        assert activar.status_code == 200, activar.text
    try:
        await _cargar_en_validador(cliente, token, lote_id)

        async def _lote_observado() -> bool:
            estado = await _estado_lote(cliente, token, lote_id)
            return bool(estado == "OBSERVADO_VALIDADOR")

        await esperar_hasta(_lote_observado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS)
    finally:
        async with httpx.AsyncClient(base_url=_URL_TEDEF_WEB, timeout=5.0) as cliente_simulador:
            restaurar = await cliente_simulador.post("/admin/falla", data={"modo": "ninguno"})
            assert restaurar.status_code == 200, restaurar.text

    resultados = await _validacion_oficial(cliente, token, lote_id)
    forma = next(r for r in resultados if r["etapa"] == "FORMA")
    assert forma["resultado"] == "CONFORME", forma
    detallada = next(r for r in resultados if r["etapa"] == "DETALLADA")
    assert detallada["resultado"] == "OBSERVADO"
    assert len(detallada["observaciones"]) >= 1
    observacion = detallada["observaciones"][0]
    assert observacion["tabla"] is not None
    assert observacion["campo"] is not None


async def prueba_8_lote_conforme_descarga_s01_con_huella(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Lote conforme": `.S01` descargado, huella registrada,
    estado VALIDADO."""

    token = await token_para_rol(NombreRol.ANALISTA)
    iafas_id = await _iafas_de_cuenta(sesion, _CUENTA_CONFORME)
    await liberar_cuenta_de_lotes_en_curso(sesion, _CUENTA_CONFORME)
    resultado = await _generar_lote(cliente, token, iafas_id, _CUENTA_CONFORME)
    assert resultado.conforme is True, resultado.cuerpo_completo
    lote_id = resultado.lote_id
    assert lote_id is not None

    await _asegurar_sesion_tedef_web_activa(sesion, cliente, token)
    await _cargar_en_validador(cliente, token, lote_id)

    async def _lote_validado() -> bool:
        estado = await _estado_lote(cliente, token, lote_id)
        assert estado != "OBSERVADO_VALIDADOR", (
            f"El lote {lote_id} quedo observado; se esperaba un lote enteramente conforme."
        )
        return bool(estado == "VALIDADO")

    await esperar_hasta(_lote_validado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS)

    detalle = await cliente.get(f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token}"})
    cuerpo = detalle.json()
    assert cuerpo["nombre_s01"] is not None
    assert cuerpo["sha256_s01"] is not None
    assert len(cuerpo["sha256_s01"]) == 64, "SHA-256 en hexadecimal: 64 caracteres."
