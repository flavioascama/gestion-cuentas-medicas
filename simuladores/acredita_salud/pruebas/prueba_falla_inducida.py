"""Prueba el modo de falla inducida y la latencia artificial (Seccion
9.1): 'caida del servicio, expiracion de sesion y respuesta vacia', y la
ruta de administracion que los activa en caliente -- lo que la Fase 11
necesita para probar que el robot detecta y reacciona a cada caso."""

from __future__ import annotations

from httpx import AsyncClient


async def prueba_modo_caida_servicio_devuelve_503(cliente_autenticado: AsyncClient) -> None:
    fijar = await cliente_autenticado.post("/admin/falla", data={"modo": "caida_servicio"})
    assert fijar.status_code == 200

    respuesta = await cliente_autenticado.get("/menu")
    assert respuesta.status_code == 503

    # La propia ruta de administracion sigue respondiendo para poder
    # revertir el modo de falla, aunque el resto del servicio este "caido".
    revertir = await cliente_autenticado.post("/admin/falla", data={"modo": "ninguno"})
    assert revertir.status_code == 200
    assert (await cliente_autenticado.get("/menu")).status_code == 200


async def prueba_modo_expiracion_sesion_fuerza_reautenticacion(
    cliente_autenticado: AsyncClient,
) -> None:
    assert (await cliente_autenticado.get("/menu")).status_code == 200

    await cliente_autenticado.post("/admin/falla", data={"modo": "expiracion_sesion"})
    respuesta = await cliente_autenticado.get("/menu")
    assert respuesta.url.path == "/ingreso"

    await cliente_autenticado.post("/admin/falla", data={"modo": "ninguno"})
    # La sesion original sigue viva: no hizo falta reautenticar, solo dejo
    # de forzarse el rechazo.
    assert (await cliente_autenticado.get("/menu")).status_code == 200


async def prueba_modo_respuesta_vacia_no_encuentra_ni_un_asegurado_real(
    cliente_autenticado: AsyncClient,
) -> None:
    await cliente_autenticado.post("/admin/falla", data={"modo": "respuesta_vacia"})
    respuesta = await cliente_autenticado.post(
        "/acreditacion/raaus", data={"tipo_documento": "1", "numero_documento": "11111111"}
    )
    assert "raaus-no-encontrado" in respuesta.text

    await cliente_autenticado.post("/admin/falla", data={"modo": "ninguno"})
    respuesta_normal = await cliente_autenticado.post(
        "/acreditacion/raaus", data={"tipo_documento": "1", "numero_documento": "11111111"}
    )
    assert "raaus-no-encontrado" not in respuesta_normal.text


async def prueba_admin_configuracion_expone_la_latencia_artificial(
    cliente_autenticado: AsyncClient,
) -> None:
    """Fase 20: las herramientas de evidencia del backend leen esta ruta
    para declarar en la cabecera de cada archivo la latencia realmente
    vigente durante esa ejecucion (Seccion 13)."""

    respuesta = await cliente_autenticado.get("/admin/configuracion")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"latencia_artificial_ms": 0}
