"""Envio por correo de las comunicaciones de la IAFAS (Tabla 42 de la tesis:
la glosa, la liquidacion y el pago llegan a la clinica "por correo
electronico y portal de la IAFAS"). El correo lleva un texto para la
persona y la comunicacion adjunta en JSON, que es lo que lee el robot de la
clinica."""

from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage

from app.auditoria import Comunicacion

registro = logging.getLogger("receptor_iafas.correo")

_TITULOS = {
    "AUDITORIA_CONFORME": "Conformidad de auditoria",
    "OBSERVACION": "Observacion de auditoria",
    "LIQUIDACION": "Liquidacion",
    "PAGO": "Aviso de pago",
}


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
        mensaje = construir_correo(comunicacion, self._remitente, self._destinatario)
        try:
            with smtplib.SMTP(self._host, self._puerto, timeout=15) as cliente:
                cliente.send_message(mensaje)
        except OSError:
            # La comunicacion ya quedo publicada en el portal; el correo es
            # un segundo canal y su falla no deshace la decision.
            registro.exception("correo_no_enviado codigo=%s", comunicacion.codigo)
