"""Tabla `comunicacion_iafas`: cada comunicacion de la IAFAS que la clinica
recibio (portal o correo), con la cuenta a la que se aplico y el resultado."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class ComunicacionIafasModelo(Base):
    __tablename__ = "comunicacion_iafas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(sa.String(20), nullable=False, unique=True)
    canal: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    tipo: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    codigo_iafas: Mapped[str] = mapped_column(sa.String(5), nullable=False)
    codigo_ipress: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    documento: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, default=dict)
    emitida_en: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    cuenta_medica_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), nullable=True, index=True
    )
    resultado: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    detalle: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    observacion_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, index=True)
    recibida_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    respuesta_remitida_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.CheckConstraint("canal IN ('PORTAL','CORREO')", name="ck_comunicacion_iafas_canal"),
        sa.CheckConstraint(
            "resultado IN ('APLICADA','NO_APLICADA')", name="ck_comunicacion_iafas_resultado"
        ),
    )
