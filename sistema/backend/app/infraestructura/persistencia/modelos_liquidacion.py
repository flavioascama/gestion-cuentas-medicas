"""Modelos SQLAlchemy de liquidacion, pago, cierre y anulacion (Seccion
5.2.4.1, Tabla 58 T-10 a T-13; CU-12 y CU-13, Fase 28). Separado de
modelos_integracion.py por el limite de 400 lineas por archivo
(GUIA_ESTILO_CODIGO.md, Seccion 3) -- mismo motivo que
modelos_observaciones.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base

ESTADOS_SOLICITUD_ANULACION = ("PENDIENTE", "APROBADA", "RECHAZADA")


class LiquidacionModelo(Base):
    """Una liquidacion por cuenta (T-10): nace con el monto comunicado
    por la aseguradora y se completa con el monto pagado cuando
    tesoreria concilia el pago (T-11)."""

    __tablename__ = "liquidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(
        sa.ForeignKey("cuenta_medica.id"), unique=True, nullable=False
    )
    es_parcial: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    monto_liquidado: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    monto_pagado: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    diferencia: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    conciliado_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class SolicitudAnulacionModelo(Base):
    """CU-13, RF-21: el analista solicita, el jefe de cuentas medicas
    aprueba o rechaza. A lo sumo una PENDIENTE por cuenta a la vez."""

    __tablename__ = "solicitud_anulacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(sa.ForeignKey("cuenta_medica.id"), nullable=False)
    motivo: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    estado: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="PENDIENTE")
    solicitado_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    solicitado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    resuelto_por: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    resuelto_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    motivo_resolucion: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','APROBADA','RECHAZADA')",
            name="ck_solicitud_anulacion_estado",
        ),
    )
