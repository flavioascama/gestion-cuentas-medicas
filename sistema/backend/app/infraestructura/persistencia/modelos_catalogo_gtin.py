"""Modelos SQLAlchemy del catalogo GTIN versionado (Seccion 6.1, 10,
Fase 17). Mismo patron que modelos_cpms.py (Fase 4/9): una version por
carga de configuracion/reglas_tedef/catalogo_gtin.yaml, nunca se
modifican versiones anteriores.

`captura`/`fila` (trazabilidad de cada producto a su imagen de origen y
numero de fila) son columnas de esta tabla, no del archivo de
configuracion (Seccion 3.3: "se transcribe... sin marcas de origen ni de
vigencia... no en el archivo de configuracion"): las escribe
herramientas/cargar_catalogo_gtin.py a partir de un mapeo propio, no de
catalogo_gtin.yaml. Son una cita de pagina y fila, no una marca de
vigencia ni de version del validador (Regla 16): no dicen "legado" ni
"provisional", solo de donde se leyo cada dato.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base


class CatalogoGtinVersionModelo(Base):
    __tablename__ = "catalogo_gtin_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruta_origen: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    cargado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    productos: Mapped[list[CatalogoGtinProductoModelo]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class CatalogoGtinProductoModelo(Base):
    __tablename__ = "catalogo_gtin_producto"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("catalogo_gtin_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(sa.String(13), nullable=False)
    tipo_codigo: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    tipo_producto_catalogo: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    tipo_producto_tedef: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    nombre: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    denominacion_comun: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    concentracion: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    forma_farmaceutica: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    captura: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    fila: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    version: Mapped[CatalogoGtinVersionModelo] = relationship(back_populates="productos")

    __table_args__ = (
        sa.UniqueConstraint(
            "version_id", "codigo", name="uq_catalogo_gtin_producto_version_codigo"
        ),
        sa.CheckConstraint(
            "tipo_producto_tedef IN ('M','P','I','R','B','A')",
            name="ck_catalogo_gtin_producto_tipo_tedef",
        ),
    )
