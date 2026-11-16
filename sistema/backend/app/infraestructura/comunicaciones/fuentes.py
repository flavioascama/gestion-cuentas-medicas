"""Lectura de las comunicaciones de la IAFAS por sus dos canales y remision
de la respuesta a una observacion por su portal. Lo mismo que haria la
persona: abrir el portal de la aseguradora y su bandeja de correo."""

from __future__ import annotations

import email
import imaplib
import json
from datetime import UTC, datetime
from email.message import EmailMessage
from email.policy import default as politica_por_defecto
from email.utils import parseaddr, parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup, Tag

from app.dominio.comunicaciones.casos_uso import ComunicacionIafas
from app.dominio.comunicaciones.correos import AdjuntoRecibido, CorreoRecibido, huella_de


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


NOMBRE_ADJUNTO_COMUNICACION = "comunicacion.json"


def _comunicacion(adjuntos: tuple[AdjuntoRecibido, ...]) -> ComunicacionIafas | None:
    """La comunicacion con el formato de la IAFAS, si el correo la trae. Un
    adjunto con ese nombre que no se puede leer no detiene la revision: el
    correo queda por revisar, como cualquier otro sin el formato."""
    for adjunto in adjuntos:
        if adjunto.nombre != NOMBRE_ADJUNTO_COMUNICACION:
            continue
        try:
            datos = json.loads(adjunto.contenido.decode("utf-8"))
            return ComunicacionIafas(
                codigo=str(datos["codigo"]),
                canal="CORREO",
                tipo=str(datos["tipo"]),
                codigo_iafas=str(datos["codigo_iafas"]),
                codigo_ipress=str(datos["codigo_ipress"]),
                documento=str(datos["documento"]),
                datos=dict(datos["datos"]),
                emitida_en=str(datos["emitida_en"]),
            )
        except (ValueError, KeyError, TypeError):
            return None
    return None


def _texto(mensaje: EmailMessage) -> str:
    cuerpo = mensaje.get_body(preferencelist=("plain", "html"))
    if cuerpo is None:
        return ""
    try:
        contenido = str(cuerpo.get_content())
    except (LookupError, ValueError):
        return ""
    if cuerpo.get_content_subtype() == "html":
        contenido = BeautifulSoup(contenido, "html.parser").get_text("\n")
    return contenido.strip()


def _adjuntos(mensaje: EmailMessage) -> tuple[AdjuntoRecibido, ...]:
    adjuntos = []
    for parte in mensaje.iter_attachments():
        contenido = parte.get_payload(decode=True)
        if isinstance(contenido, bytes):
            adjuntos.append(
                AdjuntoRecibido(
                    nombre=parte.get_filename() or "adjunto",
                    tipo=parte.get_content_type(),
                    contenido=contenido,
                )
            )
    return tuple(adjuntos)


def _fecha(mensaje: EmailMessage) -> datetime | None:
    try:
        fecha = parsedate_to_datetime(str(mensaje.get("Date", "")))
    except (TypeError, ValueError):
        return None
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=UTC)


def interpretar_correo(crudo: bytes) -> CorreoRecibido:
    """Convierte un mensaje del buzon en lo que el sistema registra de el."""
    mensaje = email.message_from_bytes(crudo, policy=politica_por_defecto)
    assert isinstance(mensaje, EmailMessage)
    adjuntos = _adjuntos(mensaje)
    return CorreoRecibido(
        huella=huella_de(crudo),
        remitente=parseaddr(str(mensaje.get("From", "")))[1].strip().lower(),
        asunto=str(mensaje.get("Subject", "")).strip(),
        fecha=_fecha(mensaje),
        texto=_texto(mensaje),
        adjuntos=adjuntos,
        comunicacion=_comunicacion(adjuntos),
    )


class FuenteCorreoImap:
    """Bandeja de la clinica por IMAP (TLS fuera de desarrollo). Lee todos
    los correos no leidos -- traigan o no una comunicacion con el formato de
    la IAFAS -- y, una vez registrados, los marca como leidos."""

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

    def leer_no_leidos(self) -> list[tuple[str, CorreoRecibido]]:
        cliente = self._conectar()
        try:
            _, datos = cliente.uid("search", "UNSEEN")
            uids = datos[0].split() if datos and datos[0] else []
            leidos = []
            for uid in uids:
                _, partes = cliente.uid("fetch", uid, "(BODY.PEEK[])")
                crudo = next(p[1] for p in partes if isinstance(p, tuple))
                leidos.append((uid.decode(), interpretar_correo(crudo)))
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
