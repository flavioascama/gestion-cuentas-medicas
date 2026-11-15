"""Modelos SQLAlchemy del contexto de observaciones/glosas (Seccion
5.2.4.2, Tabla 60; CU-08 a CU-10, Fase 26). Separado de
modelos_integracion.py por el limite de 400 lineas por archivo
(GUIA_ESTILO_CODIGO.md, Seccion 3) -- mismo motivo que
modelos_farmacia.py y modelos_plataformas.py.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base

NATURALEZAS = ("ADMINISTRATIVA", "TECNICA", "FINANCIERA")
ROLES_RESPONSABLES = ("analista", "auditor")
ESTADOS_OBSERVACION = ("ABIERTA", "RESPONDIDA")


class CatalogoMotivoObservacionModelo(Base):
    """Catalogo parametrizable de motivos (Seccion 5.2.4.2): a
    diferencia de CPMS/CIE-10/GTIN no tiene version ni fuente oficial
    externa, por eso no sigue el patron `*_version`/`*_procedimiento`
    de esos tres."""

    __tablename__ = "catalogo_motivo_observacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(sa.String(10), unique=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    naturaleza: Mapped[str] = mapped_column(sa.String(20), nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "naturaleza IN ('ADMINISTRATIVA','TECNICA','FINANCIERA')",
            name="ck_catalogo_motivo_observacion_naturaleza",
        ),
    )


class ObservacionModelo(Base):
    """Una observacion (glosa) comunicada por la aseguradora sobre una
    cuenta medica (CU-08 a CU-10)."""

    __tablename__ = "observacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuenta_medica_id: Mapped[int] = mapped_column(sa.ForeignKey("cuenta_medica.id"), nullable=False)
    motivo_codigo: Mapped[str] = mapped_column(
        sa.ForeignKey("catalogo_motivo_observacion.codigo"), nullable=False
    )
    naturaleza: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    es_parcial: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    detalle_campo_objetado: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    responsable_rol: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    responsable_usuario_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuario.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="ABIERTA")
    respuesta_texto: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    respuesta_sustento: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    registrado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    respondido_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.CheckConstraint(
            "naturaleza IN ('ADMINISTRATIVA','TECNICA','FINANCIERA')",
            name="ck_observacion_naturaleza",
        ),
        sa.CheckConstraint(
            "responsable_rol IN ('analista','auditor')", name="ck_observacion_responsable_rol"
        ),
        sa.CheckConstraint("estado IN ('ABIERTA','RESPONDIDA')", name="ck_observacion_estado"),
    )
