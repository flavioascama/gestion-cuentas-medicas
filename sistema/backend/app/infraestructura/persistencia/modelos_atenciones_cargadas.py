"""Tabla `atencion_cargada`: las atenciones cerradas del sistema
hospitalario que el administrador carga con un archivo Excel (2026-11-22).
Traen datos del paciente: la atencion completa se guarda cifrada (C-05)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.cifrado_columnas import TextoLargoCifrado


class AtencionCargadaModelo(Base):
    __tablename__ = "atencion_cargada"

    id: Mapped[int] = mapped_column(primary_key=True)
    atencion_id: Mapped[str] = mapped_column(sa.String(40), nullable=False, unique=True)
    # La atencion en el mismo formato que entrega el sistema hospitalario.
    datos: Mapped[str] = mapped_column(TextoLargoCifrado(), nullable=False)
    cargado_por: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    cargado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
