"""Tablas de la atencion importada del sistema hospitalario (2026-11-19):
los procedimientos por codificar y el copago cobrado de la cuenta."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.dominio.integracion.atencion_hospitalaria import AREAS_PROCEDIMIENTO
from app.dominio.integracion.copago_cobrado import ORIGENES_COPAGO
from app.infraestructura.persistencia.base import Base


def _en(columna: str, valores: tuple[str, ...]) -> str:
    return f"{columna} IN (" + ",".join(f"'{v}'" for v in valores) + ")"


class ProcedimientoPorCodificarModelo(Base):
    """Pendiente mientras `procedimiento_facturado_id` sea NULL; al
    confirmarlo el auditor queda enlazado al procedimiento facturado, que
    conserva asi el area de origen."""

    __tablename__ = "procedimiento_por_codificar"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descripcion: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    area: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    cantidad: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    monto_unitario: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(sa.Date, nullable=False)
    procedimiento_facturado_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("procedimiento_facturado.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    __table_args__ = (
        sa.CheckConstraint(_en("area", AREAS_PROCEDIMIENTO), name="ck_por_codificar_area"),
        sa.CheckConstraint("cantidad > 0", name="ck_por_codificar_cantidad"),
        sa.CheckConstraint("monto_unitario > 0", name="ck_por_codificar_monto"),
    )


class CopagoCobradoModelo(Base):
    __tablename__ = "copago_cobrado"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(sa.Date, nullable=False)
    referencia: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    origen: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    registrado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint("monto > 0", name="ck_copago_cobrado_monto"),
        sa.CheckConstraint(_en("origen", ORIGENES_COPAGO), name="ck_copago_cobrado_origen"),
    )
