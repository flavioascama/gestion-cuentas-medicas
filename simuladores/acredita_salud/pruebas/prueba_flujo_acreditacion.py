"""Prueba el flujo central del simulador (Seccion 9.1): ingreso, consulta
RAAUS, consulta directa por IAFAS, evaluacion de sub-coberturas, y
generacion + impresion/reimpresion del documento -- lo que en la Fase 11
va a automatizar el robot de Playwright."""

from __future__ import annotations

from httpx import AsyncClient


async def prueba_rechaza_credenciales_incorrectas(cliente: AsyncClient) -> None:
    # El usuario se valida antes que el CAPTCHA (Seccion 5.1 del manual:
    # mismo orden que los campos en pantalla), asi que un captcha_id
    # inventado no impide ver el mensaje de usuario invalido.
    respuesta = await cliente.post(
        "/ingreso",
        data={
            "usuario": "x",
            "clave": "y",
            "captcha_id": "no-existe",
            "respuesta_captcha": "AAAAA",
        },
    )
    assert respuesta.status_code == 401
    assert "error-usuario" in respuesta.text


async def prueba_redirige_al_menu_sin_sesion(cliente: AsyncClient) -> None:
    respuesta = await cliente.get("/menu")
    assert respuesta.url.path == "/ingreso"


async def prueba_ingreso_exitoso_lleva_al_menu(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.get("/menu")
    assert respuesta.status_code == 200
    assert "menu-acreditacion" in respuesta.text
    # Modulos deshabilitados de la Seccion 9.1, visibles pero no habilitados.
    assert "RMPA" in respuesta.text
    assert "menu-tedef" in respuesta.text


async def prueba_raaus_encuentra_un_asegurado_activo(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.post(
        "/acreditacion/raaus", data={"tipo_documento": "1", "numero_documento": "11111111"}
    )
    assert respuesta.status_code == 200
    assert "Ana Prueba Vigente" in respuesta.text
    assert 'data-testid="raaus-estado"' in respuesta.text
    assert ">ACTIVO<" in respuesta.text


async def prueba_raaus_no_encuentra_documento_inexistente(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.post(
        "/acreditacion/raaus", data={"tipo_documento": "1", "numero_documento": "00000000"}
    )
    assert respuesta.status_code == 200
    assert "raaus-no-encontrado" in respuesta.text


async def prueba_consulta_iafas_muestra_vigencia_y_plan(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.post(
        "/acreditacion/iafas", data={"tipo_documento": "1", "numero_documento": "11111111"}
    )
    assert respuesta.status_code == 200
    assert "PLAN DE PRUEBA" in respuesta.text
    assert "2027-01-01" in respuesta.text
    # Campos con clave fija (Fase 11): el robot los lee por su propio
    # data-testid, no por la posicion que ocupan en la tabla visible.
    assert 'data-testid="iafas-plan">PLAN DE PRUEBA<' in respuesta.text
    assert 'data-testid="iafas-vigente-hasta">2027-01-01<' in respuesta.text


async def prueba_consulta_iafas_muestra_motivo_de_cancelacion(
    cliente_autenticado: AsyncClient,
) -> None:
    respuesta = await cliente_autenticado.post(
        "/acreditacion/iafas", data={"tipo_documento": "1", "numero_documento": "22222222"}
    )
    assert respuesta.status_code == 200
    assert "CANCELADO" in respuesta.text
    assert "Prueba" in respuesta.text


async def prueba_flujo_completo_de_acreditacion_genera_documento(
    cliente_autenticado: AsyncClient,
) -> None:
    evaluar = await cliente_autenticado.get(
        "/acreditacion/evaluar", params={"tipo_documento": "1", "numero_documento": "33333333"}
    )
    assert evaluar.status_code == 200
    assert "monto-copago-fijo" in evaluar.text
    assert "25.50" in evaluar.text

    generar = await cliente_autenticado.post(
        "/acreditacion/generar", data={"tipo_documento": "1", "numero_documento": "33333333"}
    )
    assert generar.status_code == 200  # sigue el redirect (follow_redirects=True)
    assert "documento-solicitud" in generar.text
    assert "AUT0000001" in generar.text

    reimpresion = await cliente_autenticado.get(
        "/acreditacion/AUT0000001/documento?reimpresion=true"
    )
    assert "etiqueta-reimpresion" in reimpresion.text

    pdf = await cliente_autenticado.get("/acreditacion/AUT0000001/documento.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


async def prueba_generar_para_asegurado_inexistente_devuelve_404(
    cliente_autenticado: AsyncClient,
) -> None:
    respuesta = await cliente_autenticado.post(
        "/acreditacion/generar", data={"tipo_documento": "1", "numero_documento": "99999999"}
    )
    assert respuesta.status_code == 404
