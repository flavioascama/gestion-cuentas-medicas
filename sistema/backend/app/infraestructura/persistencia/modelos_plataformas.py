"""Modelos SQLAlchemy de validacion oficial y sesiones asistidas (Seccion
10 del plan v3, Fase 13). Separados de modelos_integracion.py para no
superar el limite de 400 lineas por archivo de GUIA_ESTILO_CODIGO.md.

`ValidacionOficialModelo` y `ObservacionValidadorModelo` los llena
`RegistrarResultadoValidador` (Fase 16); `SesionPlataformaModelo` lo llena
el protocolo de sesion asistida y CAPTCHA de la Seccion 8.4 (Fase 15).
Ninguna de las tres tiene todavia un caso de uso que la escriba: esta
fase solo crea el esquema, tal como lo pide el entregable de la Fase 13
(Seccion 15 del plan)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base


class ValidacionOficialModelo(Base):
    """Seccion 10: un resultado de la revision de forma o de la validacion
    detallada del validador TEDEF Web, por lote (Fase 16)."""

    __tablename__ = "validacion_oficial"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(
        sa.ForeignKey("lote_facturacion.id", ondelete="CASCADE"), nullable=False
    )
    trabajo_id: Mapped[int | None] = mapped_column(sa.ForeignKey("trabajo.id"), nullable=True)
    etapa: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    resultado: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    estado_informado_validador: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    ruta_reporte: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    sha256_reporte: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    registrado_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    observaciones: Mapped[list[ObservacionValidadorModelo]] = relationship(
        back_populates="validacion_oficial"
    )

    __table_args__ = (
        sa.CheckConstraint("etapa IN ('FORMA','DETALLADA')", name="ck_validacion_oficial_etapa"),
        sa.CheckConstraint(
            "resultado IN ('CONFORME','OBSERVADO')", name="ck_validacion_oficial_resultado"
        ),
    )


class ObservacionValidadorModelo(Base):
    """Seccion 10: una fila del reporte `.xlsx` del validador (tabla,
    linea, campo clave, campo, valor observado, codigo, descripcion),
    Seccion 9.2 del plan v3."""

    __tablename__ = "observacion_validador"

    id: Mapped[int] = mapped_column(primary_key=True)
    validacion_oficial_id: Mapped[int] = mapped_column(
        sa.ForeignKey("validacion_oficial.id", ondelete="CASCADE"), nullable=False
    )
    tabla: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    numero_linea: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    campo_clave: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    campo: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    valor_observado: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    codigo_error: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    descripcion: Mapped[str] = mapped_column(sa.String(500), nullable=False)

    validacion_oficial: Mapped[ValidacionOficialModelo] = relationship(
        back_populates="observaciones"
    )

    __table_args__ = (
        sa.Index("ix_observacion_validador_validacion_oficial_id", "validacion_oficial_id"),
    )


class SesionPlataformaModelo(Base):
    """Seccion 8.4 y 10 del plan v3: sesion asistida con CAPTCHA sobre
    ACREDITA SALUD o TEDEF Web, reutilizada por el trabajador mientras
    este ACTIVA (Fase 15)."""

    __tablename__ = "sesion_plataforma"

    id: Mapped[int] = mapped_column(primary_key=True)
    plataforma: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    estado: Mapped[str] = mapped_column(sa.String(30), nullable=False, default="SOLICITADA")
    imagen_captcha: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    # Se borra de la fila en cuanto el trabajador la consume (Seccion 8.4,
    # punto 4): nunca queda una respuesta de CAPTCHA vieja en la base.
    respuesta_captcha: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    solicitada_por: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    activa_desde: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    expira_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    motivo: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    __table_args__ = (
        sa.Index("ix_sesion_plataforma_plataforma_estado", "plataforma", "estado"),
        sa.CheckConstraint(
            "plataforma IN ('acredita_salud','tedef_web')", name="ck_sesion_plataforma_plataforma"
        ),
        sa.CheckConstraint(
            "estado IN ('SOLICITADA','ESPERANDO_CAPTCHA','CAPTCHA_RESPONDIDO','ACTIVA',"
            "'EXPIRADA','FALLIDA','CERRADA')",
            name="ck_sesion_plataforma_estado",
        ),
    )
