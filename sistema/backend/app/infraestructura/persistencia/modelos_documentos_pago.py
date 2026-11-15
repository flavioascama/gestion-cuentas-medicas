"""Tablas `nota_documento` (RI-11) y `comprobante_reemplazado` (CU-10)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base


class NotaDocumentoModelo(Base):
    """Una nota de credito o debito por comprobante (Tabla 1, campos 25 a
    29, un solo espacio de nota por documento)."""

    __tablename__ = "nota_documento"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_facturador_id: Mapped[int] = mapped_column(
        sa.ForeignKey("documento_facturador.id"), nullable=False, unique=True
    )
    tipo: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    serie: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    numero: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(sa.Date, nullable=False)
    motivo: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    registrado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    __table_args__ = (
        sa.CheckConstraint("tipo IN ('C','D')", name="ck_nota_documento_tipo"),
        sa.CheckConstraint("motivo IN ('R','A','D')", name="ck_nota_documento_motivo"),
        sa.CheckConstraint("monto > 0", name="ck_nota_documento_monto"),
    )


class ComprobanteReemplazadoModelo(Base):
    """Comprobante que dejo de estar vigente al refacturar (CU-10)."""

    __tablename__ = "comprobante_reemplazado"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_facturador_id: Mapped[int] = mapped_column(
        sa.ForeignKey("documento_facturador.id"), nullable=False, index=True
    )
    tipo_documento_pago: Mapped[str] = mapped_column(sa.String(2), nullable=False)
    serie: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    numero: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    fecha_emision: Mapped[date] = mapped_column(sa.Date, nullable=False)
    reemplazado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    reemplazado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    motivo: Mapped[str] = mapped_column(sa.String(300), nullable=False)
