"""Modelos SQLAlchemy del catalogo CPMS versionado (Seccion 6.1, 8.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base


class CpmsVersionModelo(Base):
    __tablename__ = "cpms_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    etiqueta: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    # [{"archivo": "...", "huella_sha256": "..."}, ...] (Seccion 8.2).
    archivos_origen: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, nullable=False)
    conteo: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    procedimientos: Mapped[list[CpmsProcedimientoModelo]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class CpmsProcedimientoModelo(Base):
    __tablename__ = "cpms_procedimiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpms_version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cpms_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo_grupo: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    nombre_grupo: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    codigo_seccion: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    nombre_seccion: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    codigo_subseccion: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    nombre_subseccion: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    codigo_procedimiento: Mapped[str] = mapped_column(sa.String(20), nullable=False, index=True)
    # Verificado contra el archivo real: la denominacion mas larga tiene
    # 922 caracteres (Parte 1). Se deja margen para partes futuras.
    denominacion_procedimiento: Mapped[str] = mapped_column(sa.String(1000), nullable=False)

    version: Mapped[CpmsVersionModelo] = relationship(back_populates="procedimientos")
