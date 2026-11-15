"""Prueba de TransmisorFtp contra un servidor FTP real y efimero (Seccion
7.8, punto 2): a diferencia de las demas pruebas de este archivo, esta si
habla el protocolo FTP de verdad, pero contra un servidor de prueba
levantado en el propio proceso, no contra el simulador de la Fase 8 (ese
requiere Docker y se verifica aparte, manualmente, contra el simulador
real -- docs/DECISIONES.md)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from app.infraestructura.transmision.transmisor_ftp import TransmisorFtp


@dataclass
class _ConfiguracionFtpPrueba:
    ftp_receptor_iafas_host: str
    ftp_receptor_iafas_puerto: int
    ftp_receptor_iafas_usuario: str
    ftp_receptor_iafas_clave: str
    entorno: str = "desarrollo"


@pytest.fixture
def servidor_ftp_local(tmp_path: Path) -> Iterator[_ConfiguracionFtpPrueba]:
    autorizador = DummyAuthorizer()
    autorizador.add_user("usuario_prueba", "clave_prueba", str(tmp_path), perm="elradfmw")

    manejador = FTPHandler
    manejador.authorizer = autorizador
    manejador.passive_ports = range(60000, 60010)

    servidor = FTPServer(("127.0.0.1", 0), manejador)
    puerto = servidor.address[1]
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield _ConfiguracionFtpPrueba(
            ftp_receptor_iafas_host="127.0.0.1",
            ftp_receptor_iafas_puerto=puerto,
            ftp_receptor_iafas_usuario="usuario_prueba",
            ftp_receptor_iafas_clave="clave_prueba",
        )
    finally:
        servidor.close_all()


async def prueba_transmite_un_archivo_real_por_ftp(
    servidor_ftp_local: _ConfiguracionFtpPrueba, tmp_path: Path
) -> None:
    transmisor = TransmisorFtp(servidor_ftp_local)  # type: ignore[arg-type]
    contenido = b"contenido de prueba de un .S01"

    resultado = await transmisor.transmitir("archivo_de_prueba.S01", contenido)

    assert resultado.exitosa
    assert resultado.motivo is None
    assert (tmp_path / "archivo_de_prueba.S01").read_bytes() == contenido


async def prueba_reporta_fallo_si_el_servidor_no_esta_disponible(tmp_path: Path) -> None:
    configuracion = _ConfiguracionFtpPrueba(
        ftp_receptor_iafas_host="127.0.0.1",
        ftp_receptor_iafas_puerto=1,  # puerto reservado, nada escucha ahi
        ftp_receptor_iafas_usuario="x",
        ftp_receptor_iafas_clave="x",
    )
    transmisor = TransmisorFtp(configuracion)  # type: ignore[arg-type]

    resultado = await transmisor.transmitir("archivo.S01", b"contenido")

    assert not resultado.exitosa
    assert resultado.motivo


async def prueba_fuera_de_desarrollo_no_cae_a_ftp_sin_cifrar(
    servidor_ftp_local: _ConfiguracionFtpPrueba,
) -> None:
    """RNF-15 y C-04: sin degradacion a una transferencia sin cifrar. El
    servidor de prueba no ofrece TLS: fuera de desarrollo la remision falla
    en vez de viajar en claro."""
    configuracion = _ConfiguracionFtpPrueba(
        ftp_receptor_iafas_host=servidor_ftp_local.ftp_receptor_iafas_host,
        ftp_receptor_iafas_puerto=servidor_ftp_local.ftp_receptor_iafas_puerto,
        ftp_receptor_iafas_usuario=servidor_ftp_local.ftp_receptor_iafas_usuario,
        ftp_receptor_iafas_clave=servidor_ftp_local.ftp_receptor_iafas_clave,
        entorno="produccion",
    )
    resultado = await TransmisorFtp(configuracion).transmitir("lote.S01", b"x")  # type: ignore[arg-type]
    assert resultado.exitosa is False
