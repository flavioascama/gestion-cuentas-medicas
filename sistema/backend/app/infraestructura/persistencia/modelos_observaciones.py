"""Modelos SQLAlchemy del contexto de observaciones/glosas (Seccion
5.2.4.2, Tabla 60; CU-08 a CU-10, Fase 26). Separado de
modelos_integracion.py por el limite de 400 lineas por archivo
(GUIA_ESTILO_CODIGO.md, Seccion 3) -- mismo motivo que
modelos_farmacia.py y modelos_plataformas.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infraestructura.persistencia.base import Base
from app.infraestructura.persistencia.cifrado_columnas import BinarioCifrado, TextoCifrado

NATURALEZAS = ("ADMINISTRATIVA", "TECNICA", "FINANCIERA")
ROLES_RESPONSABLES = ("analista", "auditor")
ESTADOS_OBSERVACION = ("ABIERTA", "RESPONDIDA")
RESULTADOS_OBSERVACION = ("LEVANTADA", "MANTENIDA")


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
    # 2026-11-19: lo glosado, si la aseguradora lo comunica, y en que
    # termino la observacion respondida.
    monto_observado: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    resultado: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    resultado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "naturaleza IN ('ADMINISTRATIVA','TECNICA','FINANCIERA')",
            name="ck_observacion_naturaleza",
        ),
        sa.CheckConstraint(
            "responsable_rol IN ('analista','auditor')", name="ck_observacion_responsable_rol"
        ),
        sa.CheckConstraint("estado IN ('ABIERTA','RESPONDIDA')", name="ck_observacion_estado"),
        sa.CheckConstraint(
            "resultado IS NULL OR resultado IN ('LEVANTADA','MANTENIDA')",
            name="ck_observacion_resultado",
        ),
    )


class AdjuntoRespuestaObservacionModelo(Base):
    """El PDF adjunto a la respuesta de una observacion (2026-11-22): uno
    por observacion, con el nombre y el contenido cifrados (C-05)."""

    __tablename__ = "adjunto_respuesta_observacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    observacion_id: Mapped[int] = mapped_column(
        sa.ForeignKey("observacion.id"), nullable=False, unique=True
    )
    nombre: Mapped[str] = mapped_column(TextoCifrado(), nullable=False)
    tamano: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    contenido: Mapped[bytes] = mapped_column(BinarioCifrado(), nullable=False)
    subido_por: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    subido_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
