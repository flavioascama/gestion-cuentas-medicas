"""Modelo SQLAlchemy de productos de farmacia dispensados (Seccion 6.1,
10, Fase 17): fuente de T4. Separado de modelos_integracion.py para no
superar el limite de 400 lineas por archivo (GUIA_ESTILO_CODIGO.md,
Seccion 3) -- mismo motivo que modelos_plataformas.py en la Fase 13.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class ProductoFacturadoModelo(Base):
    """T4, Seccion 10: un producto de farmacia dispensado en una cuenta
    medica. `catalogo_gtin_version_id` solo se puebla cuando `catalogo`
    vale '1' (GTIN, Seccion 16 supuesto 5: el unico catalogo con
    productos transcritos en este prototipo)."""

    __tablename__ = "producto_facturado"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), nullable=False
    )
    correlativo: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tipo_producto: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    catalogo: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    codigo_producto: Mapped[str] = mapped_column(sa.String(13), nullable=False)
    catalogo_gtin_version_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("catalogo_gtin_version.id"), nullable=True
    )
    fecha_dispensacion: Mapped[date] = mapped_column(sa.Date, nullable=False)
    cantidad_venta: Mapped[Decimal] = mapped_column(sa.Numeric(9, 2), nullable=False)
    tipo_unidad_dispensacion: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    monto_unitario_sin_impuesto: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    copago: Mapped[Decimal] = mapped_column(
        sa.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    monto_presentado: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    monto_no_cubierto: Mapped[Decimal] = mapped_column(
        sa.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    diagnostico_asociado_cie10: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)
    exento_igv: Mapped[str] = mapped_column(sa.String(1), nullable=False, default="A")
    guia_farmacia: Mapped[str | None] = mapped_column(sa.String(12), nullable=True)
    cantidad_prescrita: Mapped[Decimal | None] = mapped_column(sa.Numeric(9, 2), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "cuenta_medica_id", "correlativo", name="uq_producto_facturado_cuenta_correlativo"
        ),
        sa.CheckConstraint(
            "tipo_producto IN ('M','P','I','R','B','A')", name="ck_producto_facturado_tipo"
        ),
        sa.CheckConstraint("catalogo IN ('1','2','3','9')", name="ck_producto_facturado_catalogo"),
        sa.CheckConstraint("exento_igv IN ('A','D')", name="ck_producto_facturado_exento_igv"),
    )
