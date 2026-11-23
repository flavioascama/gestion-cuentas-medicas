"""Envio por correo de las comunicaciones de la IAFAS (Tabla 42 de la tesis:
la glosa, la liquidacion y el pago llegan a la clinica "por correo
electronico y portal de la IAFAS"). El correo lleva un texto para la
persona y la comunicacion adjunta en JSON, que es lo que lee el robot de la
clinica."""

from __future__ import annotations

import email
import imaplib
import json
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import default as politica_por_defecto

from app.auditoria import Comunicacion

registro = logging.getLogger("receptor_iafas.correo")

_TITULOS = {
    "AUDITORIA_CONFORME": "Conformidad de auditoria",
    "OBSERVACION": "Observacion de auditoria",
    "LIQUIDACION": "Liquidacion",
    "PAGO": "Aviso de pago",
}


def remitente_de(base: str, codigo_iafas: str | None) -> str:
    """Cada aseguradora escribe desde su propio buzon (auditoria.<codigo>@...),
    para que la IPRESS sepa de cual es el correo."""
    if not codigo_iafas or "@" not in base:
        return base
    usuario, dominio = base.split("@", 1)
    return f"{usuario}.{codigo_iafas}@{dominio}"


@dataclass(frozen=True, slots=True)
class CorreoRecibido:
    fecha: str
    asunto: str
    texto: str


def leer_recibidos(host: str, puerto: int, buzon: str) -> list[CorreoRecibido]:
    """Lo que la IPRESS le contesto a esa aseguradora, del mas reciente al mas
    antiguo. El servidor de correo de pruebas crea el buzon al llegarle el
    primer mensaje, con la direccion como clave; sin buzon no hay correos."""
    try:
        with imaplib.IMAP4(host, puerto, timeout=10) as cliente:
            cliente.login(buzon, buzon)
            cliente.select("INBOX", readonly=True)
            _, datos = cliente.search(None, "ALL")
            recibidos = []
            for numero in reversed(datos[0].split()):
                _, partes = cliente.fetch(numero, "(RFC822)")
                crudo = partes[0][1] if partes and isinstance(partes[0], tuple) else b""
                mensaje = email.message_from_bytes(crudo, policy=politica_por_defecto)
                cuerpo = mensaje.get_body(preferencelist=("plain",))
                recibidos.append(
                    CorreoRecibido(
                        fecha=str(mensaje["Date"] or ""),
                        asunto=str(mensaje["Subject"] or ""),
                        texto=cuerpo.get_content().strip() if cuerpo is not None else "",
                    )
                )
            return recibidos
    except (OSError, imaplib.IMAP4.error):
        return []


def construir_correo(comunicacion: Comunicacion, remitente: str, destinatario: str) -> EmailMessage:
    mensaje = EmailMessage()
    titulo = _TITULOS.get(comunicacion.tipo, comunicacion.tipo)
    mensaje["Subject"] = (
        f"[IAFAS {comunicacion.codigo_iafas}] {titulo} - comprobante {comunicacion.documento} "
        f"({comunicacion.codigo})"
    )
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["X-Comunicacion-Iafas"] = comunicacion.codigo
    lineas = [f"{titulo} del comprobante {comunicacion.documento}."]
    lineas += [f"{clave}: {valor}" for clave, valor in comunicacion.datos.items()]
    mensaje.set_content("\n".join(lineas))
    adjunto = {
        "codigo": comunicacion.codigo,
        "codigo_iafas": comunicacion.codigo_iafas,
        "codigo_ipress": comunicacion.codigo_ipress,
        "documento": comunicacion.documento,
        "tipo": comunicacion.tipo,
        "datos": comunicacion.datos,
        "emitida_en": comunicacion.emitida_en,
    }
    mensaje.add_attachment(
        json.dumps(adjunto, ensure_ascii=False, indent=2).encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="comunicacion.json",
    )
    return mensaje


class EnviadorCorreoSmtp:
    def __init__(self, host: str, puerto: int, remitente: str, destinatario: str) -> None:
        self._host = host
        self._puerto = puerto
        self._remitente = remitente
        self._destinatario = destinatario

    def __call__(self, comunicacion: Comunicacion) -> None:
        remitente = remitente_de(self._remitente, comunicacion.codigo_iafas)
        mensaje = construir_correo(comunicacion, remitente, self._destinatario)
        try:
            with smtplib.SMTP(self._host, self._puerto, timeout=15) as cliente:
                cliente.send_message(mensaje)
        except OSError:
            # La comunicacion ya quedo publicada en el portal; el correo es
            # un segundo canal y su falla no deshace la decision.
            registro.exception("correo_no_enviado codigo=%s", comunicacion.codigo)

    def enviar_libre(
        self, asunto: str, texto: str, adjuntar_documento: bool, codigo_iafas: str | None = None
    ) -> None:
        """Correo que el personal de la IAFAS escribe fuera del formato de
        comunicaciones (2026-11-15): un pedido de documentacion, una consulta
        o una carta, con o sin un documento PDF. La clinica lo recibe en su
        buzon y su sistema lo deja por revisar."""
        remitente = remitente_de(self._remitente, codigo_iafas)
        mensaje = construir_correo_libre(
            remitente, self._destinatario, asunto, texto, adjuntar_documento
        )
        with smtplib.SMTP(self._host, self._puerto, timeout=15) as cliente:
            cliente.send_message(mensaje)


def _escapar_pdf(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generar_documento_pdf(lineas: list[str]) -> bytes:
    """Un PDF de una pagina con las lineas dadas, sin depender de ninguna
    libreria: basta para representar el documento que adjunta la IAFAS."""
    texto = " ".join(f"({_escapar_pdf(linea)}) Tj T*" for linea in lineas)
    flujo = f"BT /F1 11 Tf 50 780 Td 16 TL {texto} ET".encode("latin-1", "replace")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += str(numero).encode() + b" 0 obj\n" + objeto + b"\nendobj\n"
    inicio_tabla = len(salida)
    salida += b"xref\n0 " + str(len(objetos) + 1).encode() + b"\n0000000000 65535 f \n"
    for posicion in posiciones:
        salida += f"{posicion:010d} 00000 n \n".encode()
    salida += b"trailer\n<< /Size " + str(len(objetos) + 1).encode() + b" /Root 1 0 R >>\n"
    salida += b"startxref\n" + str(inicio_tabla).encode() + b"\n%%EOF\n"
    return bytes(salida)


def construir_correo_libre(
    remitente: str, destinatario: str, asunto: str, texto: str, adjuntar_documento: bool
) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje.set_content(texto)
    if adjuntar_documento:
        mensaje.add_attachment(
            generar_documento_pdf([asunto, "", *texto.splitlines()]),
            maintype="application",
            subtype="pdf",
            filename="documento_iafas.pdf",
        )
    return mensaje
