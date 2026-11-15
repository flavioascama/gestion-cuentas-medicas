from __future__ import annotations

from app.captcha import GestorCaptcha


def prueba_genera_imagen_png_valida() -> None:
    gestor = GestorCaptcha()
    captcha = gestor.generar()
    imagen = gestor.imagen_png(captcha.id)
    assert imagen is not None
    assert imagen.startswith(b"\x89PNG")


def prueba_verifica_sin_distinguir_mayusculas() -> None:
    gestor = GestorCaptcha()
    captcha = gestor.generar()
    assert gestor.verificar_y_consumir(captcha.id, captcha.texto.lower())


def prueba_rechaza_respuesta_incorrecta() -> None:
    gestor = GestorCaptcha()
    captcha = gestor.generar()
    assert not gestor.verificar_y_consumir(captcha.id, "XXXXX")


def prueba_es_de_un_solo_uso() -> None:
    gestor = GestorCaptcha()
    captcha = gestor.generar()
    assert gestor.verificar_y_consumir(captcha.id, captcha.texto)
    assert not gestor.verificar_y_consumir(captcha.id, captcha.texto)


def prueba_id_desconocido_no_tiene_imagen() -> None:
    gestor = GestorCaptcha()
    assert gestor.imagen_png("no-existe") is None
