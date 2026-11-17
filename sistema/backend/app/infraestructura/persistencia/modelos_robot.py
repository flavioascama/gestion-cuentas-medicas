"""Tablas `opcion_sistema` y `paso_robot`.

`opcion_sistema` guarda opciones que el administrador cambia en caliente
(hoy una: si la navegacion del robot queda visible). `paso_robot` guarda una
captura del navegador del robot por cada paso de un trabajo; la imagen puede
mostrar datos del asegurado y va cifrada (C-05, C-12)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.cifrado_columnas import BinarioCifrado


class OpcionSistemaModelo(Base):
    __tablename__ = "opcion_sistema"

    clave: Mapped[str] = mapped_column(sa.String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    actualizado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class PasoRobotModelo(Base):
    __tablename__ = "paso_robot"

    id: Mapped[int] = mapped_column(primary_key=True)
    trabajo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("trabajo.id", ondelete="CASCADE"), nullable=False
    )
    orden: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    plataforma: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    descripcion: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    # Sin cadena de consulta (navegacion_robot.url_sin_consulta).
    url: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    capturado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    captura: Mapped[bytes] = mapped_column(BinarioCifrado(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("trabajo_id", "orden", name="uq_paso_robot_trabajo_orden"),
        sa.Index("ix_paso_robot_capturado_en", "capturado_en"),
    )
