"""Configuracion del simulador, leida de variables de entorno.

Aplicacion independiente (Regla 0.5): no importa nada de sistema/backend/,
asi que no comparte el modulo Configuracion del backend aunque el patron
sea el mismo (pydantic-settings no es dependencia de este simulador
justamente para mantenerlo minimo; se usa os.environ directo).
"""

from __future__ import annotations

import os
from pathlib import Path


def _entero(nombre: str, por_defecto: int) -> int:
    valor = os.environ.get(nombre)
    return int(valor) if valor else por_defecto


class Configuracion:
    ftp_usuario: str = os.environ.get("FTP_USUARIO", "ipress_local")
    ftp_clave: str = os.environ.get("FTP_CLAVE", "")
    ftp_puerto: int = _entero("FTP_PUERTO", 21)
    ftp_puertos_pasivos_desde: int = _entero("FTP_PUERTOS_PASIVOS_DESDE", 30000)
    ftp_puertos_pasivos_hasta: int = _entero("FTP_PUERTOS_PASIVOS_HASTA", 30009)
    # Dentro del contenedor la IP publica no se conoce; se anuncia el host
    # (o IP) por el que el cliente FTP externo puede alcanzar los puertos
    # pasivos publicados (ver docker-compose.yml de este simulador).
    ftp_direccion_enmascarada: str | None = os.environ.get("FTP_DIRECCION_ENMASCARADA") or None
    portal_puerto: int = _entero("PORTAL_PUERTO", 8000)
    bandeja_entrada: Path = Path(os.environ.get("BANDEJA_ENTRADA", "/datos/bandeja_entrada"))
    base_datos: Path = Path(os.environ.get("BASE_DATOS", "/datos/receptor_iafas.sqlite3"))
    # Seccion 9.3: claves_iafas.json, para descifrar el .S01 (solo lectura,
    # el mismo archivo que usa simuladores/tedef_web/ para cifrarlo).
    datos_semilla: Path = Path(os.environ.get("RUTA_SIMULADORES_DATOS_SEMILLA", "/datos_semilla"))
    # Correo de la IAFAS (simuladores/correo): sin SMTP_HOST, las
    # comunicaciones solo se publican en el portal.
    smtp_host: str = os.environ.get("SMTP_HOST", "")
    smtp_puerto: int = _entero("SMTP_PUERTO", 3025)
    # Buzon donde cada aseguradora lee lo que la IPRESS le contesta.
    imap_puerto: int = _entero("IMAP_PUERTO", 3143)
    correo_remitente: str = os.environ.get("CORREO_REMITENTE", "auditoria@iafas.test")
    correo_destino_ipress: str = os.environ.get(
        "CORREO_DESTINO_IPRESS", "cuentasmedicas@clinica.test"
    )


configuracion = Configuracion()
