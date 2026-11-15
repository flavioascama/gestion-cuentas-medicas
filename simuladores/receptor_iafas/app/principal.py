"""Punto de entrada del simulador: arranca el servidor FTP en un hilo y el
portal web en el hilo principal, ambos en el mismo contenedor (Seccion 9:
'aplicaciones independientes, con dependencias y contenedor propios').
Comparten la misma instancia de AlmacenamientoReceptor para que el portal
vea de inmediato lo que el FTP acaba de procesar.
"""

from __future__ import annotations

import json
import logging
import threading

import uvicorn

from app.almacenamiento import AlmacenamientoReceptor
from app.auditoria import AuditoriaIafas
from app.configuracion import configuracion
from app.correo import EnviadorCorreoSmtp
from app.portal_web import construir_app
from app.servidor_ftp import construir_servidor

logging.basicConfig(level=logging.INFO)


def _cargar_claves_iafas() -> dict[str, str]:
    ruta = configuracion.datos_semilla / "claves_iafas.json"
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    claves: dict[str, str] = contenido["claves"]
    return claves


def main() -> None:
    almacenamiento = AlmacenamientoReceptor(configuracion.base_datos)
    claves_iafas = _cargar_claves_iafas()
    enviador = (
        EnviadorCorreoSmtp(
            configuracion.smtp_host,
            configuracion.smtp_puerto,
            configuracion.correo_remitente,
            configuracion.correo_destino_ipress,
        )
        if configuracion.smtp_host
        else None
    )
    auditoria = AuditoriaIafas(configuracion.base_datos, enviador)

    servidor_ftp = construir_servidor(almacenamiento, claves_iafas, auditoria)
    hilo_ftp = threading.Thread(target=servidor_ftp.serve_forever, daemon=True)
    hilo_ftp.start()
    logging.getLogger("receptor_iafas").info(
        "servidor_ftp_iniciado puerto=%s bandeja=%s",
        configuracion.ftp_puerto,
        configuracion.bandeja_entrada,
    )

    app = construir_app(almacenamiento, auditoria)
    uvicorn.run(app, host="0.0.0.0", port=configuracion.portal_puerto)


if __name__ == "__main__":
    main()
