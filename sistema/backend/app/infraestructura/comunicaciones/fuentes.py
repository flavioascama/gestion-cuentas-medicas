"""Lectura de las comunicaciones de la IAFAS por sus dos canales y remision
de la respuesta a una observacion por su portal. Lo mismo que haria la
persona: abrir el portal de la aseguradora y su bandeja de correo."""

from __future__ import annotations

import email
import imaplib
import json
from email.message import Message
from email.policy import default as politica_por_defecto
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from app.dominio.comunicaciones.casos_uso import ComunicacionIafas


class ErrorFuenteComunicaciones(Exception):
    pass


class FuentePortalIafas:
    def __init__(self, url_base: str, tiempo_espera: float = 30.0) -> None:
        self._url_base = url_base.rstrip("/")
        self._tiempo_espera = tiempo_espera

    async def codigos(self, codigo_ipress: str) -> list[str]:
        async with httpx.AsyncClient(timeout=self._tiempo_espera) as cliente:
            respuesta = await cliente.get(
                f"{self._url_base}/comunicaciones", params={"ipress": codigo_ipress}
            )
        respuesta.raise_for_status()
        sopa = BeautifulSoup(respuesta.text, "html.parser")
        return [
            str(fila["data-codigo"])
            for fila in sopa.find_all(attrs={"data-testid": "fila-comunicacion"})
            if isinstance(fila, Tag)
        ]

    async def obtener(self, codigo: str) -> ComunicacionIafas:
        async with httpx.AsyncClient(timeout=self._tiempo_espera) as cliente:
            respuesta = await cliente.get(f"{self._url_base}/comunicaciones/{codigo}")
        respuesta.raise_for_status()
        sopa = BeautifulSoup(respuesta.text, "html.parser")
        detalle = sopa.find(attrs={"data-testid": "detalle-comunicacion"})
        datos = sopa.find(attrs={"data-testid": "datos-comunicacion"})
        if not isinstance(detalle, Tag) or not isinstance(datos, Tag):
            raise ErrorFuenteComunicaciones(f"La pagina de {codigo} no tiene el detalle esperado.")
        return ComunicacionIafas(
            codigo=str(detalle["data-codigo"]),
            canal="PORTAL",
            tipo=str(detalle["data-tipo"]),
            codigo_iafas=str(detalle["data-iafas"]),
            codigo_ipress=str(detalle["data-ipress"]),
            documento=str(detalle["data-documento"]),
            datos=json.loads(datos.get_text()),
            emitida_en=str(detalle["data-emitida"]),
        )

    async def responder(
        self, codigo: str, codigo_ipress: str, respuesta: str, sustento: str | None
    ) -> None:
        async with httpx.AsyncClient(timeout=self._tiempo_espera) as cliente:
            resultado = await cliente.post(
                f"{self._url_base}/comunicaciones/{codigo}/respuesta",
                data={
                    "codigo_ipress": codigo_ipress,
                    "respuesta": respuesta,
                    "sustento": sustento or "",
                },
            )
        if resultado.status_code >= 400:
            raise ErrorFuenteComunicaciones(
                f"La IAFAS no recibio la respuesta a {codigo}: {resultado.text[:200]}"
            )


def _adjunto_comunicacion(mensaje: Message) -> dict[str, Any] | None:
    for parte in mensaje.walk():
        if parte.get_filename() == "comunicacion.json":
            contenido = parte.get_payload(decode=True)
            if isinstance(contenido, bytes):
                datos: dict[str, Any] = json.loads(contenido.decode("utf-8"))
                return datos
    return None


class FuenteCorreoImap:
    """Bandeja de la clinica por IMAP (TLS fuera de desarrollo). Lee los
    correos no leidos que traen una comunicacion adjunta y, una vez
    procesados, los marca como leidos."""

    def __init__(self, host: str, puerto: int, usuario: str, clave: str, usar_tls: bool) -> None:
        self._host, self._puerto = host, puerto
        self._usuario, self._clave = usuario, clave
        self._usar_tls = usar_tls

    def _conectar(self) -> imaplib.IMAP4:
        cliente = (
            imaplib.IMAP4_SSL(self._host, self._puerto)
            if self._usar_tls
            else imaplib.IMAP4(self._host, self._puerto)
        )
        cliente.login(self._usuario, self._clave)
        cliente.select("INBOX")
        return cliente

    def leer_no_leidos(self) -> list[tuple[str, ComunicacionIafas]]:
        cliente = self._conectar()
        try:
            _, datos = cliente.uid("search", "UNSEEN")
            uids = datos[0].split() if datos and datos[0] else []
            leidos = []
            for uid in uids:
                _, partes = cliente.uid("fetch", uid, "(BODY.PEEK[])")
                crudo = next(p[1] for p in partes if isinstance(p, tuple))
                mensaje = email.message_from_bytes(crudo, policy=politica_por_defecto)
                adjunto = _adjunto_comunicacion(mensaje)
                if adjunto is None:
                    continue
                leidos.append(
                    (
                        uid.decode(),
                        ComunicacionIafas(
                            codigo=adjunto["codigo"],
                            canal="CORREO",
                            tipo=adjunto["tipo"],
                            codigo_iafas=adjunto["codigo_iafas"],
                            codigo_ipress=adjunto["codigo_ipress"],
                            documento=adjunto["documento"],
                            datos=adjunto["datos"],
                            emitida_en=adjunto["emitida_en"],
                        ),
                    )
                )
            return leidos
        finally:
            cliente.logout()

    def marcar_leidos(self, uids: list[str]) -> None:
        if not uids:
            return
        cliente = self._conectar()
        try:
            for uid in uids:
                cliente.uid("store", uid, "+FLAGS", "(\\Seen)")
        finally:
            cliente.logout()
