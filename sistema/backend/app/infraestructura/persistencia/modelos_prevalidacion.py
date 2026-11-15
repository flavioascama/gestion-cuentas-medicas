"""Modelos SQLAlchemy del informe de prevalidacion (Seccion 8.2, Fase 18:
`GET /lotes/{id}/prevalidacion`). Separado de modelos_integracion.py para
no superar el limite de 400 lineas por archivo (GUIA_ESTILO_CODIGO.md,
Seccion 3).

Antes de la Fase 18, `GenerarLote` devolvia `InformeValidacionLote` solo
en memoria, a quien lo invocaba en el momento -- sin lugar para
consultarlo despues. Estas dos tablas le dan persistencia, con la misma
forma que `validacion_oficial`/`observacion_validador` (Seccion 10) para
el informe del validador oficial. Solo existen para lotes conformes: un
lote no conforme nunca llega a `lote_facturacion` (GenerarLote solo
persiste lotes conformes), asi que tampoco tiene por que persistir su
informe -- ya viaja completo en la respuesta de `POST /lotes`."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base


class InformePrevalidacionModelo(Base):
    __tablename__ = "informe_prevalidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        sa.ForeignKey("lote_facturacion.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    conforme: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    generado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    hallazgos: Mapped[list[HallazgoPrevalidacionModelo]] = relationship(
        back_populates="informe", cascade="all, delete-orphan"
    )


class HallazgoPrevalidacionModelo(Base):
    """Seccion 7.6: un error o una advertencia de un campo concreto, con
    el criterio literal que lo origina (mismo contenido que `Hallazgo`,
    `app/dominio/integracion/hallazgos.py`)."""

    __tablename__ = "hallazgo_prevalidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    informe_id: Mapped[int] = mapped_column(
        sa.ForeignKey("informe_prevalidacion.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severidad: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    tabla: Mapped[str] = mapped_column(sa.String(5), nullable=False)
    campo_numero: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    campo_nombre: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    criterio_id: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    criterio_texto: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    valor: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    mensaje: Mapped[str] = mapped_column(sa.String(500), nullable=False)

    informe: Mapped[InformePrevalidacionModelo] = relationship(back_populates="hallazgos")

    __table_args__ = (
        sa.CheckConstraint(
            "severidad IN ('error','advertencia')", name="ck_hallazgo_prevalidacion_severidad"
        ),
    )
