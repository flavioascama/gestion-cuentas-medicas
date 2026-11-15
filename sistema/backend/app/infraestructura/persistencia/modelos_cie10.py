"""Modelos SQLAlchemy del catalogo CIE-10 versionado (T2 campo 18,
"Primer Diagnostico"). Mismo patron que `modelos_cpms.py` (Seccion 8.2):
version con huella SHA-256 del archivo de origen, nunca modifica
versiones anteriores."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base


class Cie10VersionModelo(Base):
    __tablename__ = "cie10_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruta_origen: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    huella_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    conteo: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    codigos: Mapped[list[Cie10CodigoModelo]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class Cie10CodigoModelo(Base):
    """Solo codigos a nivel de subcategoria (criterio C3 del campo): 4
    caracteres (subcategoria estandar de la OMS) o 5 (extension propia
    del MINSA). El campo del Anexo 1 mide 5 caracteres; los codigos de 6
    que trae el catalogo del MINSA no caben y se excluyen al cargar."""

    __tablename__ = "cie10_codigo"

    id: Mapped[int] = mapped_column(primary_key=True)
    cie10_version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cie10_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(sa.String(5), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(sa.String(300), nullable=False)

    version: Mapped[Cie10VersionModelo] = relationship(back_populates="codigos")

    __table_args__ = (
        sa.UniqueConstraint("cie10_version_id", "codigo", name="uq_cie10_codigo_version_codigo"),
    )
