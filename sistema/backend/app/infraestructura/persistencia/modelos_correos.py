"""Tablas `correo_iafas` y `adjunto_correo_iafas`: cada correo que llego al
buzon de cuentas medicas de la clinica, con su estado de revision y sus
adjuntos. El asunto, el texto y el nombre y el contenido de los adjuntos
pueden traer datos del asegurado: se guardan cifrados (C-05)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.cifrado_columnas import (
    BinarioCifrado,
    TextoCifrado,
    TextoLargoCifrado,
)


class CorreoIafasModelo(Base):
    __tablename__ = "correo_iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    huella_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    remitente: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    codigo_iafas: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)
    asunto: Mapped[str] = mapped_column(TextoLargoCifrado(), nullable=False)
    texto: Mapped[str] = mapped_column(TextoLargoCifrado(), nullable=False)
    fecha_correo: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    recibido_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(sa.String(12), nullable=False, index=True)
    motivo_revision: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    comunicacion_codigo: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    cuenta_medica_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), nullable=True, index=True
    )
    resuelto_por: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)
    resuelto_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    nota_resolucion: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "estado IN ('PROCESADO','POR_REVISAR','VINCULADO','DESCARTADO')",
            name="ck_correo_iafas_estado",
        ),
    )


class AdjuntoCorreoIafasModelo(Base):
    __tablename__ = "adjunto_correo_iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    correo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("correo_iafas.id"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    tipo: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    tamano: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    huella_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # Con valor: el adjunto no se almaceno (tipo no permitido o excede el
    # limite) y `contenido` queda vacio.
    motivo_omision: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    contenido: Mapped[bytes | None] = mapped_column(BinarioCifrado(), nullable=True)


class RespuestaCorreoIafasModelo(Base):
    """Lo que la clinica le contesta a la IAFAS por correo (2026-11-22). El
    texto puede traer datos del asegurado: se guarda cifrado (C-05)."""

    __tablename__ = "respuesta_correo_iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    correo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("correo_iafas.id"), nullable=False, index=True
    )
    texto: Mapped[str] = mapped_column(TextoLargoCifrado(), nullable=False)
    respondido_por: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    respondido_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    # Nulo mientras el correo aun no sale del buzon de la clinica.
    enviada_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
