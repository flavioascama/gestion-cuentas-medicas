"""Tablas `opcion_sistema`, `paso_robot` y `cuadro_robot`.

`opcion_sistema` guarda opciones que el administrador cambia en caliente (si
la navegacion del robot queda visible y de que modo). `paso_robot` es el
registro de lo que hizo el robot en cada trabajo, sin imagenes.
`cuadro_robot` tiene, mientras un trabajo esta en curso, lo que el navegador
del robot muestra en ese momento: una sola imagen por trabajo, cifrada
(C-05, C-12) porque puede mostrar datos del asegurado, que se borra al
terminar."""

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

    __table_args__ = (
        sa.UniqueConstraint("trabajo_id", "orden", name="uq_paso_robot_trabajo_orden"),
        sa.Index("ix_paso_robot_capturado_en", "capturado_en"),
    )


class CuadroRobotModelo(Base):
    __tablename__ = "cuadro_robot"

    trabajo_id: Mapped[int] = mapped_column(
        sa.ForeignKey("trabajo.id", ondelete="CASCADE"), primary_key=True
    )
    # Sin cadena de consulta (navegacion_robot.url_sin_consulta).
    url: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    cuadro: Mapped[bytes] = mapped_column(BinarioCifrado(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
