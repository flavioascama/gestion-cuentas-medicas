"""Tabla `parametro_sistema`: el valor que el administrador fijo para un
parametro del sistema. Sin fila, rige el de la configuracion del despliegue."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class ParametroSistemaModelo(Base):
    __tablename__ = "parametro_sistema"

    clave: Mapped[str] = mapped_column(sa.String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(sa.Text, nullable=False)
    actualizado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
