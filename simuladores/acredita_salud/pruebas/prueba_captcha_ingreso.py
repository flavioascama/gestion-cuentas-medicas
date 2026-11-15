"""CAPTCHA de la pantalla de ingreso (Seccion 9.1, 5.1 del manual, 8.4):
un mensaje distinto por cada validacion, y la ruta de administracion que
solo responde con SIMULADOR_MODO_PRUEBA=true (la fixture `cliente` la deja
en true, ver conftest.py)."""

from __future__ import annotations

import re

from httpx import AsyncClient

from app.configuracion import configuracion

_PATRON_CAPTCHA_ID = re.compile(r'name="captcha_id" value="([^"]+)"')


async def prueba_ingreso_muestra_una_imagen_de_captcha(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/ingreso")
    assert respuesta.status_code == 200
    assert 'data-testid="imagen-captcha"' in respuesta.text
    coincidencia = _PATRON_CAPTCHA_ID.search(respuesta.text)
    assert coincidencia is not None
    captcha_id = coincidencia.group(1)

    imagen = await cliente.get(f"/captcha/{captcha_id}.png")
    assert imagen.status_code == 200
    assert imagen.headers["content-type"] == "image/png"
    assert imagen.content.startswith(b"\x89PNG")


async def prueba_rechaza_captcha_incorrecto_con_credenciales_correctas(
    cliente: AsyncClient,
) -> None:
    pagina = await cliente.get("/ingreso")
    captcha_id = _PATRON_CAPTCHA_ID.search(pagina.text).group(1)  # type: ignore[union-attr]

    respuesta = await cliente.post(
        "/ingreso",
        data={
            "usuario": configuracion.usuario,
            "clave": configuracion.clave,
            "captcha_id": captcha_id,
            "respuesta_captcha": "ZZZZZ",
        },
    )
    assert respuesta.status_code == 401
    assert "error-captcha" in respuesta.text
    assert "Debe Ingresar captcha completo" in respuesta.text


async def prueba_rechaza_contrasena_incorrecta_antes_que_el_captcha(cliente: AsyncClient) -> None:
    respuesta = await cliente.post(
        "/ingreso",
        data={
            "usuario": configuracion.usuario,
            "clave": "clave-equivocada",
            "captcha_id": "no-existe",
            "respuesta_captcha": "AAAAA",
        },
    )
    assert respuesta.status_code == 401
    assert "error-clave" in respuesta.text
    assert "Debe Ingresar una contraseña válido" in respuesta.text


async def prueba_captcha_es_de_un_solo_uso(cliente: AsyncClient) -> None:
    pagina = await cliente.get("/ingreso")
    captcha_id = _PATRON_CAPTCHA_ID.search(pagina.text).group(1)  # type: ignore[union-attr]
    respuesta_texto = await cliente.get(f"/admin/captcha/{captcha_id}")
    texto = respuesta_texto.text

    datos = {
        "usuario": configuracion.usuario,
        "clave": configuracion.clave,
        "captcha_id": captcha_id,
        "respuesta_captcha": texto,
    }
    primera = await cliente.post("/ingreso", data=datos)
    assert primera.status_code == 200  # exito, sigue el redirect a /menu

    await cliente.post("/salir")
    segunda = await cliente.post("/ingreso", data=datos)
    assert segunda.status_code == 401


async def prueba_admin_captcha_no_responde_sin_modo_prueba(cliente: AsyncClient) -> None:
    valor_original = configuracion.simulador_modo_prueba
    configuracion.simulador_modo_prueba = False
    try:
        pagina = await cliente.get("/ingreso")
        captcha_id = _PATRON_CAPTCHA_ID.search(pagina.text).group(1)  # type: ignore[union-attr]
        respuesta = await cliente.get(f"/admin/captcha/{captcha_id}")
        assert respuesta.status_code == 403
    finally:
        configuracion.simulador_modo_prueba = valor_original


async def prueba_admin_captcha_sin_id_devuelve_el_texto_del_mas_reciente(
    cliente: AsyncClient,
) -> None:
    """Fase 20: una prueba de integracion que responde el CAPTCHA por la
    API (Seccion 8.4) actua como el usuario humano, sin abrir un
    navegador -- no conoce el `captcha_id` que el robot Playwright genero
    al abrir /ingreso, asi que necesita esta variante sin id."""

    primera_pagina = await cliente.get("/ingreso")
    primer_id = _PATRON_CAPTCHA_ID.search(primera_pagina.text).group(1)  # type: ignore[union-attr]
    segunda_pagina = await cliente.get("/ingreso")
    segundo_id = _PATRON_CAPTCHA_ID.search(segunda_pagina.text).group(1)  # type: ignore[union-attr]
    assert primer_id != segundo_id

    texto_del_segundo = (await cliente.get(f"/admin/captcha/{segundo_id}")).text
    respuesta = await cliente.get("/admin/captcha")
    assert respuesta.status_code == 200
    assert respuesta.text == texto_del_segundo


async def prueba_admin_captcha_sin_id_sin_ninguno_vigente_da_404(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/admin/captcha")
    assert respuesta.status_code == 404
