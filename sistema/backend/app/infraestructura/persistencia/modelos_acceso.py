"""Modelos SQLAlchemy de la Seccion 6.1: usuario, rol, usuario_rol.

Los cuatro roles son un conjunto cerrado (ver dominio/acceso/entidades.py);
se siembran por migracion, no se crean desde la API.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infraestructura.persistencia.base import Base

tabla_usuario_rol = sa.Table(
    "usuario_rol",
    Base.metadata,
    sa.Column("usuario_id", sa.ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("rol_id", sa.ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True),
)


class RolModelo(Base):
    __tablename__ = "rol"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(20), unique=True, nullable=False)


class UsuarioModelo(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_usuario: Mapped[str] = mapped_column(sa.String(50), unique=True, nullable=False)
    nombres: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    hash_clave: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    # Control C-01 (Seccion 5.2.7): bloqueo tras cinco intentos fallidos.
    intentos_fallidos: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    roles: Mapped[list[RolModelo]] = relationship(secondary=tabla_usuario_rol, lazy="selectin")


class TokenRevocadoModelo(Base):
    """Control C-01: lista de revocacion de credenciales de sesion (AD-06
    revisada en la Fase 22, docs/DECISIONES.md). Una fila por token
    revocado -- al cerrar sesion o al desactivar un usuario -- con su
    propio vencimiento, para poder purgarla despues de esa fecha sin
    perder la capacidad de rechazar un token todavia vigente."""

    __tablename__ = "token_revocado"

    jti: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    expira_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revocado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
