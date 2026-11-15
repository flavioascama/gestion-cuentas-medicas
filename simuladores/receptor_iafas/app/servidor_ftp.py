"""Servidor FTP local (Seccion 9.2, punto 1): recibe el .S01 en un
directorio de entrada, con credenciales por variable de entorno. Al
terminar de recibir cada archivo, lo procesa de inmediato (Seccion 9.2,
punto 2) y guarda el resultado para que el portal lo liste.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from app.almacenamiento import AlmacenamientoReceptor
from app.auditoria import AuditoriaIafas
from app.configuracion import configuracion
from app.procesador import procesar_lote

registro = logging.getLogger("receptor_iafas.ftp")


def _construir_manejador(
    almacenamiento: AlmacenamientoReceptor,
    claves_iafas: dict[str, str],
    auditoria: AuditoriaIafas | None = None,
) -> type[FTPHandler]:
    class ManejadorReceptor(FTPHandler):
        def on_file_received(self, file: str) -> None:
            ruta = Path(file)
            resultado = procesar_lote(ruta, claves_iafas)
            almacenamiento.registrar(
                nombre_archivo=ruta.name,
                estado=resultado.estado,
                motivo=resultado.motivo,
                numero_lote=resultado.numero_lote,
                codigo_iafas=resultado.codigo_iafas,
                codigo_ipress=resultado.codigo_ipress,
            )
            if auditoria is not None and resultado.estado == "ACEPTADO":
                auditoria.registrar_documentos(
                    ruta.name,
                    resultado.codigo_iafas or "",
                    resultado.codigo_ipress or "",
                    list(resultado.documentos),
                )
            registro.info("lote_recibido", extra={"archivo": ruta.name, "estado": resultado.estado})

    return ManejadorReceptor


def construir_servidor(
    almacenamiento: AlmacenamientoReceptor,
    claves_iafas: dict[str, str],
    auditoria: AuditoriaIafas | None = None,
) -> FTPServer:
    configuracion.bandeja_entrada.mkdir(parents=True, exist_ok=True)

    autorizador = DummyAuthorizer()
    autorizador.add_user(
        configuracion.ftp_usuario,
        configuracion.ftp_clave,
        str(configuracion.bandeja_entrada),
        perm="elradfmw",
    )

    manejador = _construir_manejador(almacenamiento, claves_iafas, auditoria)
    manejador.authorizer = autorizador
    manejador.passive_ports = range(
        configuracion.ftp_puertos_pasivos_desde, configuracion.ftp_puertos_pasivos_hasta + 1
    )
    if configuracion.ftp_direccion_enmascarada:
        manejador.masquerade_address = configuracion.ftp_direccion_enmascarada

    return FTPServer(("0.0.0.0", configuracion.ftp_puerto), manejador)
