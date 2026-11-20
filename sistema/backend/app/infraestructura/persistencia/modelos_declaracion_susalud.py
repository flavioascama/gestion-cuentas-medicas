"""Tabla `declaracion_susalud_sin_facturacion`: el mes en que la clinica no
remitio lotes y presento a SUSALUD la declaracion jurada. El sistema solo
deja constancia de que se presento (Resolucion 043-2025-SUSALUD/S)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class DeclaracionSusaludSinFacturacionModelo(Base):
    __tablename__ = "declaracion_susalud_sin_facturacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo: Mapped[str] = mapped_column(sa.String(6), nullable=False, unique=True)
    registrada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    registrada_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
