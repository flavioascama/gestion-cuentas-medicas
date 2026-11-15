"""Adaptador TransmisorFtp del puerto Transmisor (Seccion 7.8, punto 2).

Requisito 15 / supuesto de la Seccion 14, punto 7: "Se implementa FTPS
cuando el receptor lo admite, con caida controlada a FTP simple contra el
simulador local, mas huella SHA-256 del archivo". El simulador local
(Fase 8, simuladores/receptor_iafas) no ofrece TLS -- es un prototipo
deterministico, no un servidor productivo -- asi que en la practica esta
clase siempre cae a FTP simple contra el, pero intenta FTPS primero para
que el mismo adaptador sirva sin cambios si algun dia el receptor lo admite.
La huella SHA-256 la verifica quien llama (RemitirLote), no este adaptador.

`ftplib` es la unica libreria de este archivo que toca el dominio del
"transporte" (Seccion 5.2: dominio/ no puede importarla, por eso vive aqui).
"""

from __future__ import annotations

import asyncio
import ftplib
import io

import structlog

from app.compartido.configuracion import Configuracion
from app.dominio.integracion.puertos import ResultadoTransmision, Transmisor

registro = structlog.get_logger(__name__)


class TransmisorFtp(Transmisor):
    def __init__(self, configuracion: Configuracion) -> None:
        self._configuracion = configuracion

    async def transmitir(self, nombre_archivo: str, contenido: bytes) -> ResultadoTransmision:
        # ftplib es sincrono/bloqueante; se corre en un hilo aparte para no
        # bloquear el bucle de eventos del backend asincrono.
        try:
            return await asyncio.to_thread(self._transmitir_sincrono, nombre_archivo, contenido)
        except ftplib.all_errors as error:
            registro.warning(
                "remision_ftp_fallida", nombre_archivo=nombre_archivo, error=str(error)
            )
            return ResultadoTransmision(exitosa=False, motivo=str(error))

    def _transmitir_sincrono(self, nombre_archivo: str, contenido: bytes) -> ResultadoTransmision:
        cfg = self._configuracion
        cliente = self._conectar(cfg)
        try:
            cliente.storbinary(f"STOR {nombre_archivo}", io.BytesIO(contenido))
        finally:
            try:
                cliente.quit()
            except ftplib.all_errors:
                cliente.close()
        registro.info("remision_ftp_exitosa", nombre_archivo=nombre_archivo)
        return ResultadoTransmision(exitosa=True, motivo=None)

    def _conectar(self, cfg: Configuracion) -> ftplib.FTP:
        try:
            cliente_tls = ftplib.FTP_TLS(timeout=30)
            cliente_tls.connect(cfg.ftp_receptor_iafas_host, cfg.ftp_receptor_iafas_puerto)
            cliente_tls.auth()  # sube el canal de control a TLS antes de autenticar
            cliente_tls.login(cfg.ftp_receptor_iafas_usuario, cfg.ftp_receptor_iafas_clave)
            cliente_tls.prot_p()
            return cliente_tls
        except ftplib.all_errors:
            # RNF-15 y C-04: "sin degradacion a una transferencia sin
            # cifrar". La caida a FTP simple solo se admite en el entorno
            # de desarrollo, cuyo receptor de prueba no ofrece TLS
            # explicito (supuesto 7, Seccion 14); en cualquier otro entorno
            # la remision falla en vez de viajar sin cifrar (2026-11-13).
            if cfg.entorno != "desarrollo":
                raise
            cliente = ftplib.FTP(timeout=30)
            cliente.connect(cfg.ftp_receptor_iafas_host, cfg.ftp_receptor_iafas_puerto)
            cliente.login(cfg.ftp_receptor_iafas_usuario, cfg.ftp_receptor_iafas_clave)
            return cliente
