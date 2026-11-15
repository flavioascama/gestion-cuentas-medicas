"""Tabla `carta_garantia` (RF-13, CU-06): una carta por cuenta."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class CartaGarantiaModelo(Base):
    __tablename__ = "carta_garantia"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), nullable=False, unique=True
    )
    numero: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    vigente_desde: Mapped[date] = mapped_column(sa.Date, nullable=False)
    vigente_hasta: Mapped[date] = mapped_column(sa.Date, nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    registrado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    __table_args__ = (
        sa.CheckConstraint("vigente_hasta >= vigente_desde", name="ck_carta_garantia_vigencia"),
        sa.CheckConstraint("monto > 0", name="ck_carta_garantia_monto"),
    )
