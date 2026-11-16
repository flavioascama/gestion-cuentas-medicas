"""Escenarios de integracion del registro de los correos de la IAFAS
(2026-11-15), contra el simulador del receptor de la IAFAS, el servidor de
correo simulado y el robot de comunicaciones.

- Un correo libre con un PDF, escrito por el personal de la aseguradora,
  queda por revisar con un aviso; el analista lee su texto, descarga el
  adjunto y lo vincula a una cuenta, y el hecho queda en su historial.
- Un correo con el formato de la IAFAS enviado desde un buzon que no esta
  registrado (una suplantacion) no registra el pago: queda por revisar y el
  analista lo descarta.
- Un correo del remitente registrado sobre un comprobante que la clinica no
  conoce queda por revisar con un aviso, en vez de perderse.

Requiere el stack completo y los simuladores (incluido simuladores/correo);
se ejecuta con pytest dentro del contenedor del backend.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any

import httpx
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_comunicaciones import ComunicacionIafasModelo
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, EventoModelo
from pruebas_integracion.prueba_ciclo_comunicaciones_iafas import _cabecera, _revisar_hasta
from pruebas_integracion.prueba_sesion_asistida_y_cobertura import _TokenParaRol

_URL_RECEPTOR_IAFAS = "http://receptor-iafas:8000"
_REMITENTE_IAFAS = "auditoria@iafas.test"
_BUZON_CLINICA = "cuentasmedicas@clinica.test"
_AVISO = "CORREO_IAFAS_POR_REVISAR"


async def _registrar_remitente(cliente: AsyncClient, administrador: str) -> str:
    """El administrador registra el buzon de la aseguradora; devuelve el
    codigo de una IAFAS con ese remitente."""
    listado = await cliente.get("/parametros/iafas", headers=_cabecera(administrador))
    assert listado.status_code == 200, listado.text
    for iafas in listado.json():
        respuesta = await cliente.put(
            f"/parametros/iafas/{iafas['iafas_id']}/correo-remitente",
            json={"correo_remitente": _REMITENTE_IAFAS},
            headers=_cabecera(administrador),
        )
        assert respuesta.status_code == 200, respuesta.text
    return str(listado.json()[0]["codigo"])


async def _iafas_escribe_correo_libre(asunto: str, texto: str) -> None:
    """El personal de la aseguradora escribe un correo fuera de su formato
    de comunicaciones, con su documento en PDF."""
    async with httpx.AsyncClient(base_url=_URL_RECEPTOR_IAFAS, timeout=15.0) as simulador:
        respuesta = await simulador.post(
            "/admin/correo", data={"asunto": asunto, "texto": texto, "adjuntar_documento": "1"}
        )
    assert respuesta.status_code == 303, respuesta.text


def _enviar(mensaje: EmailMessage) -> None:
    anfitrion = os.environ.get("CORREO_IMAP_HOST", "correo")
    with smtplib.SMTP(anfitrion, 3025, timeout=15) as servidor:
        servidor.send_message(mensaje)


async def _llega_con_formato(remitente: str, asunto: str, comunicacion: dict[str, Any]) -> None:
    """Un correo con la comunicacion adjunta en el formato de la IAFAS,
    entregado directamente al buzon de la clinica."""
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = _BUZON_CLINICA
    mensaje.set_content("Comunicación adjunta.")
    mensaje.add_attachment(
        json.dumps(comunicacion).encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="comunicacion.json",
    )
    await asyncio.to_thread(_enviar, mensaje)


def _comunicacion(codigo: str, codigo_iafas: str, tipo: str, documento: str) -> dict[str, Any]:
    return {
        "codigo": codigo,
        "tipo": tipo,
        "codigo_iafas": codigo_iafas,
        "codigo_ipress": "15995250",
        "documento": documento,
        "datos": {"monto_pagado": "999999.00", "monto_liquidado": "999999.00"},
        "emitida_en": "2026-11-15T09:00:00",
    }


async def _correo_por_revisar(cliente: AsyncClient, token: str, asunto: str) -> dict[str, Any]:
    encontrados: list[dict[str, Any]] = []

    async def _llego() -> bool:
        respuesta = await cliente.get(
            "/correos-iafas", params={"estado": "POR_REVISAR"}, headers=_cabecera(token)
        )
        assert respuesta.status_code == 200, respuesta.text
        encontrados[:] = [c for c in respuesta.json() if c["asunto"] == asunto]
        return bool(encontrados)

    await _revisar_hasta(cliente, token, _llego)
    return encontrados[0]


async def _avisos_de_correo(cliente: AsyncClient, token: str) -> set[int]:
    respuesta = await cliente.get("/avisos", params={"limite": 500}, headers=_cabecera(token))
    assert respuesta.status_code == 200, respuesta.text
    return {
        int(aviso["datos"]["correo_id"])
        for aviso in respuesta.json()
        if aviso["tipo_evento"] == _AVISO
    }


async def _eventos(sesion: AsyncSession, tipo_evento: str, correo_id: int) -> list[EventoModelo]:
    filas = await sesion.execute(
        sa.select(EventoModelo).where(EventoModelo.tipo_evento == tipo_evento)
    )
    return [e for e in filas.scalars().all() if e.datos.get("correo_id") == correo_id]


async def prueba_correo_libre_con_pdf_queda_por_revisar_y_se_vincula_a_la_cuenta(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    analista = await token_para_rol(NombreRol.ANALISTA)
    await _registrar_remitente(cliente, await token_para_rol(NombreRol.ADMINISTRADOR))
    asunto = f"Solicitud de documentación adicional {uuid.uuid4().hex[:10]}"
    texto = "Para continuar con la auditoría necesitamos el informe médico y la orden."
    await _iafas_escribe_correo_libre(asunto, texto)

    correo = await _correo_por_revisar(cliente, analista, asunto)
    assert correo["remitente"] == _REMITENTE_IAFAS
    assert correo["motivo_revision"] == "SIN_FORMATO"
    assert correo["cantidad_adjuntos"] == 1
    assert correo["id"] in await _avisos_de_correo(cliente, analista)

    ruta = f"/correos-iafas/{correo['id']}"
    detalle = (await cliente.get(ruta, headers=_cabecera(analista))).json()
    assert detalle["texto"] == texto
    (adjunto,) = detalle["adjuntos"]
    assert adjunto["nombre"] == "documento_iafas.pdf" and adjunto["almacenado"]
    descarga = await cliente.get(f"{ruta}/adjuntos/{adjunto['id']}", headers=_cabecera(analista))
    assert descarga.status_code == 200
    assert descarga.content.startswith(b"%PDF")
    assert hashlib.sha256(descarga.content).hexdigest() == adjunto["huella"]
    assert await _eventos(sesion, "CORREO_IAFAS_CONSULTADO", correo["id"])
    assert await _eventos(sesion, "ADJUNTO_CORREO_IAFAS_DESCARGADO", correo["id"])

    cuenta_id, identificacion = (
        await sesion.execute(
            sa.select(CuentaMedicaModelo.id, CuentaMedicaModelo.identificacion_interna).limit(1)
        )
    ).one()
    vinculado = await cliente.post(
        f"{ruta}/vinculacion",
        json={"identificacion_interna": identificacion},
        headers=_cabecera(analista),
    )
    assert vinculado.status_code == 200, vinculado.text
    assert vinculado.json()["estado"] == "VINCULADO"
    assert vinculado.json()["cuenta_medica_id"] == cuenta_id
    (evento,) = await _eventos(sesion, "CORREO_IAFAS_VINCULADO", correo["id"])
    assert evento.cuenta_medica_id == cuenta_id
    assert evento.datos["huella"] == correo["huella"]
    de_la_cuenta = await cliente.get(
        "/correos-iafas", params={"cuenta_id": cuenta_id}, headers=_cabecera(analista)
    )
    assert correo["id"] in {c["id"] for c in de_la_cuenta.json()}
    assert correo["id"] not in await _avisos_de_correo(cliente, analista)


async def prueba_comunicacion_de_un_remitente_no_registrado_no_se_aplica_sola(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    analista = await token_para_rol(NombreRol.ANALISTA)
    codigo_iafas = await _registrar_remitente(
        cliente, await token_para_rol(NombreRol.ADMINISTRADOR)
    )
    codigo = f"FALSA-{uuid.uuid4().hex[:10]}"
    asunto = f"Aviso de pago {codigo}"
    # Un buzon ajeno comunica un pago con el formato de la aseguradora.
    await _llega_con_formato(
        "auditoria@iafas-falsa.test",
        asunto,
        _comunicacion(codigo, codigo_iafas, "PAGO", "F00100000001"),
    )

    correo = await _correo_por_revisar(cliente, analista, asunto)
    assert correo["motivo_revision"] == "REMITENTE_NO_REGISTRADO"
    assert correo["comunicacion_codigo"] is None and correo["cuenta_medica_id"] is None
    registrada = await sesion.scalar(
        sa.select(ComunicacionIafasModelo.id).where(ComunicacionIafasModelo.codigo == codigo)
    )
    assert registrada is None
    assert correo["id"] in await _avisos_de_correo(cliente, analista)

    descartado = await cliente.post(
        f"/correos-iafas/{correo['id']}/descarte",
        json={"motivo": "El remitente no es la aseguradora"},
        headers=_cabecera(analista),
    )
    assert descartado.status_code == 200, descartado.text
    assert descartado.json()["estado"] == "DESCARTADO"
    (evento,) = await _eventos(sesion, "CORREO_IAFAS_DESCARTADO", correo["id"])
    assert evento.datos["motivo"] == "El remitente no es la aseguradora"
    assert correo["id"] not in await _avisos_de_correo(cliente, analista)


async def prueba_correo_de_un_comprobante_desconocido_queda_por_revisar_con_aviso(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    analista = await token_para_rol(NombreRol.ANALISTA)
    codigo_iafas = await _registrar_remitente(
        cliente, await token_para_rol(NombreRol.ADMINISTRADOR)
    )
    codigo = f"DESC-{uuid.uuid4().hex[:10]}"
    asunto = f"Liquidación {codigo}"
    await _llega_con_formato(
        _REMITENTE_IAFAS, asunto, _comunicacion(codigo, codigo_iafas, "LIQUIDACION", "ZZZ999999999")
    )

    correo = await _correo_por_revisar(cliente, analista, asunto)
    assert correo["motivo_revision"] == "COMPROBANTE_DESCONOCIDO"
    assert correo["comunicacion_codigo"] == codigo
    assert correo["cuenta_medica_id"] is None
    resultado = await sesion.scalar(
        sa.select(ComunicacionIafasModelo.resultado).where(ComunicacionIafasModelo.codigo == codigo)
    )
    assert resultado == "NO_APLICADA"
    assert correo["id"] in await _avisos_de_correo(cliente, analista)
