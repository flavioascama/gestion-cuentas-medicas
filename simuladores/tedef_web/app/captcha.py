"""CAPTCHA generado con Pillow (Seccion 9.2: "usuario, contrasena y
CAPTCHA"; Seccion 9.1 lo describe como "imagen con texto y boton de
refresco"). Desafios en memoria del propio proceso, de un solo uso y con
vencimiento corto: alcanza para un simulador de pruebas deterministas, sin
necesitar persistencia entre reinicios.
"""

from __future__ import annotations

import io
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

# Sin caracteres ambiguos (0/O, 1/I): el manual no exige un alfabeto
# concreto, pero un CAPTCHA simulado no necesita ser dificil de leer.
_ALFABETO = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
_LONGITUD = 5
_VIGENCIA = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class Captcha:
    id: str
    texto: str
    expira_en: datetime


class GestorCaptcha:
    def __init__(self) -> None:
        self._desafios: dict[str, Captcha] = {}

    def generar(self) -> Captcha:
        identificador = secrets.token_urlsafe(12)
        texto = "".join(secrets.choice(_ALFABETO) for _ in range(_LONGITUD))
        captcha = Captcha(id=identificador, texto=texto, expira_en=datetime.now() + _VIGENCIA)
        self._desafios[identificador] = captcha
        return captcha

    def imagen_png(self, identificador: str) -> bytes | None:
        captcha = self._desafios.get(identificador)
        if captcha is None or datetime.now() > captcha.expira_en:
            return None
        return _dibujar(captcha.texto)

    def verificar_y_consumir(self, identificador: str, respuesta: str) -> bool:
        captcha = self._desafios.pop(identificador, None)
        if captcha is None or datetime.now() > captcha.expira_en:
            return False
        return respuesta.strip().upper() == captcha.texto

    def texto_vigente(self, identificador: str) -> str | None:
        """Seccion 8.4: "los simuladores exponen una ruta de
        administracion que devuelve el texto del CAPTCHA vigente solo si
        SIMULADOR_MODO_PRUEBA=true" -- nunca lo usa el robot."""

        captcha = self._desafios.get(identificador)
        if captcha is None or datetime.now() > captcha.expira_en:
            return None
        return captcha.texto

    def texto_del_mas_reciente(self) -> str | None:
        """Fase 20: una prueba de integracion que actua como "usuario
        humano" (Seccion 8.4) sin abrir un navegador nunca conoce el
        `captcha_id` que el robot genero al abrir `/ingreso` -- ese id no
        se persiste en el backend (solo la imagen). `dict` preserva el
        orden de insercion desde Python 3.7, asi que el ultimo desafio
        generado es el que el robot esta esperando que se responda (solo
        hay una sesion en curso por plataforma a la vez, Seccion 8.4)."""

        for captcha in reversed(self._desafios.values()):
            if datetime.now() <= captcha.expira_en:
                return captcha.texto
        return None


def _dibujar(texto: str) -> bytes:
    ancho, alto = 160, 60
    imagen = Image.new("RGB", (ancho, alto), color=(238, 238, 238))
    dibujo = ImageDraw.Draw(imagen)
    fuente = ImageFont.load_default(size=32)
    for indice, caracter in enumerate(texto):
        dibujo.text((12 + indice * 28, 10), caracter, fill=(20, 30, 60), font=fuente)
    for y in (15, 30, 45):
        dibujo.line([(0, y), (ancho, y)], fill=(190, 190, 190), width=1)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
