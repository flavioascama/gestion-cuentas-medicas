"""crea modelo de integracion: asegurado iafas ipress cuenta lote evento medicion

Revision ID: ab8ce7d4a79e
Revises: 49683855e285
Create Date: 2026-09-16 02:10:57.581196

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab8ce7d4a79e"
down_revision: str | Sequence[str] | None = "49683855e285"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "iafas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=5), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("periodicidad_remision_dias", sa.Integer(), nullable=False),
        sa.Column("ventana_monitoreo_horas", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "ipress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruc", sa.String(length=11), nullable=False),
        sa.Column("codigo_ipress", sa.String(length=8), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_ipress"),
        sa.UniqueConstraint("ruc"),
    )
    op.create_table(
        "maestro_iafas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=5), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("ficticio", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "maestro_ipress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruc", sa.String(length=11), nullable=False),
        sa.Column("codigo_ipress", sa.String(length=8), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("ficticio", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_ipress"),
        sa.UniqueConstraint("ruc"),
    )
    op.create_table(
        "asegurado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=1), nullable=False),
        sa.Column("numero_documento", sa.String(length=15), nullable=False),
        sa.Column("nombres", sa.String(length=150), nullable=False),
        sa.Column("apellidos", sa.String(length=150), nullable=False),
        sa.Column("iafas_id", sa.Integer(), nullable=False),
        sa.Column("ficticio", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["iafas_id"], ["iafas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tipo_documento", "numero_documento", name="uq_asegurado_documento"),
    )
    op.create_table(
        "lote_facturacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=7), nullable=False),
        sa.Column("iafas_id", sa.Integer(), nullable=False),
        sa.Column("periodo", sa.String(length=6), nullable=False),
        sa.Column("generado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("nombre_archivo_s01", sa.String(length=200), nullable=False),
        sa.Column("huella_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["iafas_id"], ["iafas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iafas_id", "numero", name="uq_lote_iafas_numero"),
    )
    op.create_table(
        "cuenta_medica",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identificacion_interna", sa.String(length=10), nullable=False),
        sa.Column("asegurado_id", sa.Integer(), nullable=False),
        sa.Column("iafas_id", sa.Integer(), nullable=False),
        sa.Column("ipress_id", sa.Integer(), nullable=False),
        sa.Column("fecha_prestacion", sa.Date(), nullable=False),
        sa.Column("hora_prestacion", sa.Time(), nullable=False),
        sa.Column("numero_historia_clinica", sa.String(length=8), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "estado IN ('REGISTRADA','FACTURADA','ENVIADA','RECHAZADA')",
            name="ck_cuenta_medica_estado",
        ),
        sa.ForeignKeyConstraint(["asegurado_id"], ["asegurado.id"]),
        sa.ForeignKeyConstraint(["iafas_id"], ["iafas.id"]),
        sa.ForeignKeyConstraint(["ipress_id"], ["ipress.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identificacion_interna"),
    )
    op.create_table(
        "acreditacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cuenta_id", sa.Integer(), nullable=False),
        sa.Column("condicion_cobertura", sa.String(length=20), nullable=False),
        sa.Column("codigo_autorizacion", sa.String(length=20), nullable=False),
        sa.Column("tipo_documento_autorizacion", sa.String(length=2), nullable=False),
        sa.Column("codigo_asegurado", sa.String(length=20), nullable=False),
        sa.Column("tipo_afiliacion", sa.String(length=1), nullable=False),
        sa.Column("plan", sa.String(length=100), nullable=True),
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("tipo_copago", sa.String(length=20), nullable=True),
        sa.Column("monto_copago_fijo", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("porcentaje_coaseguro", sa.Integer(), nullable=True),
        sa.Column("preexistencias", sa.JSON(), nullable=False),
        sa.Column("instante", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duracion_ms", sa.Integer(), nullable=False),
        sa.Column("componente_ejecutor", sa.String(length=50), nullable=False),
        sa.Column("ruta_evidencia", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["cuenta_id"], ["cuenta_medica.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cuenta_id"),
    )
    op.create_table(
        "documento_facturador",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cuenta_id", sa.Integer(), nullable=False),
        sa.Column("ipress_id", sa.Integer(), nullable=False),
        sa.Column("tipo_documento_pago", sa.String(length=2), nullable=False),
        sa.Column("serie", sa.String(length=4), nullable=False),
        sa.Column("numero", sa.String(length=8), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("fecha_primer_envio", sa.Date(), nullable=True),
        sa.Column("correlativo_prestacion", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cuenta_id"], ["cuenta_medica.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ipress_id"], ["ipress.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cuenta_id"),
        sa.UniqueConstraint(
            "ipress_id", "tipo_documento_pago", "serie", "numero", name="uq_documento_serie_numero"
        ),
    )
    op.create_table(
        "evento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cuenta_medica_id", sa.Integer(), nullable=True),
        sa.Column("tipo_evento", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("estado_previo", sa.String(length=20), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=20), nullable=True),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cuenta_medica_id"], ["cuenta_medica.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "medicion_paso",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cuenta_medica_id", sa.Integer(), nullable=True),
        sa.Column("lote_id", sa.Integer(), nullable=True),
        sa.Column("paso", sa.String(length=50), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duracion_ms", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["cuenta_medica_id"], ["cuenta_medica.id"]),
        sa.ForeignKeyConstraint(["lote_id"], ["lote_facturacion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "procedimiento_facturado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cuenta_id", sa.Integer(), nullable=False),
        sa.Column("descripcion_registrada", sa.String(length=500), nullable=False),
        sa.Column("tipo_clasificacion", sa.String(length=2), nullable=False),
        sa.Column("codigo_asignado", sa.String(length=20), nullable=False),
        sa.Column("cpms_version_id", sa.Integer(), nullable=False),
        sa.Column("origen_codigo", sa.String(length=50), nullable=False),
        sa.Column("usuario_confirmo_id", sa.Integer(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("monto_unitario", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("correlativo", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cpms_version_id"], ["cpms_version.id"]),
        sa.ForeignKeyConstraint(["cuenta_id"], ["cuenta_medica.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_confirmo_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "lote_documento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["documento_id"], ["documento_facturador.id"]),
        sa.ForeignKeyConstraint(["lote_id"], ["lote_facturacion.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lote_id", "documento_id", name="uq_lote_documento"),
    )

    # Seccion 6.2: 'evento sin UPDATE ni DELETE, garantizado por disparador
    # y por permisos del rol de aplicacion' (RF-16).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_evento_inmutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'La tabla evento es de solo insercion (Seccion 6.2): % no esta permitido', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evento_sin_update
        BEFORE UPDATE ON evento
        FOR EACH ROW EXECUTE FUNCTION fn_evento_inmutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evento_sin_delete
        BEFORE DELETE ON evento
        FOR EACH ROW EXECUTE FUNCTION fn_evento_inmutable();
        """
    )

    # Seccion 6.2: 'fecha_primer_envio protegida por disparador que impide
    # su sobrescritura'. Permite fijarla la primera vez (NULL -> valor);
    # rechaza cualquier cambio posterior a un valor distinto.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_proteger_fecha_primer_envio() RETURNS trigger AS $$
        BEGIN
            IF OLD.fecha_primer_envio IS NOT NULL
               AND NEW.fecha_primer_envio IS DISTINCT FROM OLD.fecha_primer_envio THEN
                RAISE EXCEPTION
                    'fecha_primer_envio no se puede sobrescribir una vez fijada (Seccion 6.2)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_proteger_fecha_primer_envio
        BEFORE UPDATE ON documento_facturador
        FOR EACH ROW EXECUTE FUNCTION fn_proteger_fecha_primer_envio();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_proteger_fecha_primer_envio ON documento_facturador;")
    op.execute("DROP FUNCTION IF EXISTS fn_proteger_fecha_primer_envio();")
    op.execute("DROP TRIGGER IF EXISTS trg_evento_sin_delete ON evento;")
    op.execute("DROP TRIGGER IF EXISTS trg_evento_sin_update ON evento;")
    op.execute("DROP FUNCTION IF EXISTS fn_evento_inmutable();")

    op.drop_table("lote_documento")
    op.drop_table("procedimiento_facturado")
    op.drop_table("medicion_paso")
    op.drop_table("evento")
    op.drop_table("documento_facturador")
    op.drop_table("acreditacion")
    op.drop_table("cuenta_medica")
    op.drop_table("lote_facturacion")
    op.drop_table("asegurado")
    op.drop_table("maestro_ipress")
    op.drop_table("maestro_iafas")
    op.drop_table("ipress")
    op.drop_table("iafas")
