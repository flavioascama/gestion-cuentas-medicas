"""correos recibidos de las IAFAS, con sus adjuntos y el remitente registrado

Cada correo que llega al buzon de cuentas medicas se registra una vez
(2026-11-15), tambien el que no trae una comunicacion con el formato de la
IAFAS: queda por revisar hasta que una persona lo vincula a una cuenta o lo
descarta. El asunto, el texto y el nombre y contenido de los adjuntos se
guardan cifrados (C-05). `iafas.correo_remitente` es el remitente del que se
aceptan comunicaciones de esa aseguradora. El rol de aplicacion recibe sus
permisos por los privilegios por defecto de la migracion d5e6f7a8b9c0.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-11-15 21:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("iafas", sa.Column("correo_remitente", sa.String(200), nullable=True))
    op.create_table(
        "correo_iafas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("huella_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("remitente", sa.String(200), nullable=False),
        sa.Column("codigo_iafas", sa.String(5), nullable=True),
        sa.Column("asunto", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("fecha_correo", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("motivo_revision", sa.String(30), nullable=True),
        sa.Column("comunicacion_codigo", sa.String(20), nullable=True),
        sa.Column(
            "cuenta_medica_id", sa.Integer(), sa.ForeignKey("cuenta_medica.id"), nullable=True
        ),
        sa.Column("resuelto_por", sa.String(60), nullable=True),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nota_resolucion", sa.String(300), nullable=True),
        sa.CheckConstraint(
            "estado IN ('PROCESADO','POR_REVISAR','VINCULADO','DESCARTADO')",
            name="ck_correo_iafas_estado",
        ),
    )
    op.create_index("ix_correo_iafas_cuenta_medica_id", "correo_iafas", ["cuenta_medica_id"])
    op.create_index("ix_correo_iafas_estado", "correo_iafas", ["estado"])
    op.create_table(
        "adjunto_correo_iafas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correo_id", sa.Integer(), sa.ForeignKey("correo_iafas.id"), nullable=False),
        sa.Column("nombre", sa.String(500), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("huella_sha256", sa.String(64), nullable=False),
        sa.Column("motivo_omision", sa.String(20), nullable=True),
        sa.Column("contenido", sa.LargeBinary(), nullable=True),
    )
    op.create_index("ix_adjunto_correo_iafas_correo_id", "adjunto_correo_iafas", ["correo_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_adjunto_correo_iafas_correo_id", table_name="adjunto_correo_iafas")
    op.drop_table("adjunto_correo_iafas")
    op.drop_index("ix_correo_iafas_estado", table_name="correo_iafas")
    op.drop_index("ix_correo_iafas_cuenta_medica_id", table_name="correo_iafas")
    op.drop_table("correo_iafas")
    op.drop_column("iafas", "correo_remitente")
