"""Add lead reference IDs, batch numbers, and Google Sheets sync metadata.

Revision ID: 20260610_0003
Revises: 20260609_0002
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260610_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


sequence_type = sa.Enum(
    "batch",
    "lead_reference",
    "form_lead",
    "delivery",
    name="sequence_type",
)


def upgrade() -> None:
    op.create_table(
        "id_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sequence_type", sequence_type, nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("date_key", sa.String(length=8), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_id_sequences_type_scope_date",
        "id_sequences",
        ["sequence_type", "scope", "date_key"],
        unique=True,
    )

    op.add_column("lead_signals", sa.Column("lead_reference_id", sa.String(40), nullable=True))
    op.add_column("lead_signals", sa.Column("batch_number", sa.String(40), nullable=True))
    op.add_column("lead_signals", sa.Column("batch_date", sa.Date(), nullable=True))
    op.add_column("lead_signals", sa.Column("source_category", sa.String(120), nullable=True))
    op.add_column("lead_signals", sa.Column("source_name", sa.String(255), nullable=True))
    op.add_column(
        "lead_signals",
        sa.Column("source_captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lead_signals",
        sa.Column(
            "exported_to_master_sheet",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "lead_signals",
        sa.Column("master_sheet_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("lead_signals", sa.Column("master_sheet_row_number", sa.Integer(), nullable=True))

    op.add_column("ingestion_runs", sa.Column("batch_number", sa.String(40), nullable=True))
    op.add_column("ingestion_runs", sa.Column("batch_date", sa.Date(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("import_mode", sa.String(80), nullable=True))
    op.add_column("ingestion_runs", sa.Column("adapter_name", sa.String(255), nullable=True))
    op.add_column("ingestion_runs", sa.Column("query_filter_used", sa.Text(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("raw_artifact_path", sa.Text(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("raw_artifact_hash", sa.String(64), nullable=True))
    op.add_column("ingestion_runs", sa.Column("operator", sa.String(120), nullable=True))

    op.add_column("form_leads", sa.Column("form_lead_ref_id", sa.String(40), nullable=True))
    op.add_column("form_leads", sa.Column("linked_lead_reference_id", sa.String(40), nullable=True))
    op.add_column("form_leads", sa.Column("batch_number", sa.String(40), nullable=True))
    op.add_column(
        "form_leads",
        sa.Column(
            "exported_to_master_sheet",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "form_leads",
        sa.Column("master_sheet_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("form_leads", sa.Column("master_sheet_row_number", sa.Integer(), nullable=True))

    op.add_column("lead_deliveries", sa.Column("delivery_id", sa.String(40), nullable=True))
    op.add_column("lead_deliveries", sa.Column("batch_number", sa.String(40), nullable=True))

    _backfill_lead_signals()
    _backfill_ingestion_runs()
    _backfill_form_leads()
    _backfill_lead_deliveries()
    _backfill_sequence_table()

    op.alter_column("lead_signals", "lead_reference_id", nullable=False)
    op.alter_column("lead_signals", "batch_number", nullable=False)
    op.create_unique_constraint(
        "uq_lead_signals_lead_reference_id", "lead_signals", ["lead_reference_id"]
    )

    op.alter_column("ingestion_runs", "batch_number", nullable=False)
    op.create_unique_constraint(
        "uq_ingestion_runs_batch_number",
        "ingestion_runs",
        ["batch_number"],
    )

    op.alter_column("form_leads", "form_lead_ref_id", nullable=False)
    op.create_unique_constraint(
        "uq_form_leads_form_lead_ref_id",
        "form_leads",
        ["form_lead_ref_id"],
    )

    op.alter_column("lead_deliveries", "delivery_id", nullable=False)
    op.create_unique_constraint(
        "uq_lead_deliveries_delivery_id",
        "lead_deliveries",
        ["delivery_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_lead_deliveries_delivery_id", "lead_deliveries", type_="unique")
    op.drop_constraint("uq_form_leads_form_lead_ref_id", "form_leads", type_="unique")
    op.drop_constraint("uq_ingestion_runs_batch_number", "ingestion_runs", type_="unique")
    op.drop_constraint("uq_lead_signals_lead_reference_id", "lead_signals", type_="unique")

    op.drop_column("lead_deliveries", "batch_number")
    op.drop_column("lead_deliveries", "delivery_id")

    op.drop_column("form_leads", "master_sheet_row_number")
    op.drop_column("form_leads", "master_sheet_synced_at")
    op.drop_column("form_leads", "exported_to_master_sheet")
    op.drop_column("form_leads", "batch_number")
    op.drop_column("form_leads", "linked_lead_reference_id")
    op.drop_column("form_leads", "form_lead_ref_id")

    op.drop_column("ingestion_runs", "operator")
    op.drop_column("ingestion_runs", "raw_artifact_hash")
    op.drop_column("ingestion_runs", "raw_artifact_path")
    op.drop_column("ingestion_runs", "query_filter_used")
    op.drop_column("ingestion_runs", "adapter_name")
    op.drop_column("ingestion_runs", "import_mode")
    op.drop_column("ingestion_runs", "batch_date")
    op.drop_column("ingestion_runs", "batch_number")

    op.drop_column("lead_signals", "master_sheet_row_number")
    op.drop_column("lead_signals", "master_sheet_synced_at")
    op.drop_column("lead_signals", "exported_to_master_sheet")
    op.drop_column("lead_signals", "source_captured_at")
    op.drop_column("lead_signals", "source_name")
    op.drop_column("lead_signals", "source_category")
    op.drop_column("lead_signals", "batch_date")
    op.drop_column("lead_signals", "batch_number")
    op.drop_column("lead_signals", "lead_reference_id")

    op.drop_index("uq_id_sequences_type_scope_date", table_name="id_sequences")
    op.drop_table("id_sequences")
    sequence_type.drop(op.get_bind(), checkfirst=True)


def _backfill_lead_signals() -> None:
    op.execute(
        """
        WITH numbered AS (
            SELECT
                ls.id,
                upper(coalesce(ls.state, 'ALL')) AS scope,
                to_char(coalesce(ls.created_at::date, ls.signal_date, current_date), 'YYYYMMDD')
                    AS date_key,
                row_number() OVER (
                    PARTITION BY upper(coalesce(ls.state, 'ALL')),
                    to_char(coalesce(ls.created_at::date, ls.signal_date, current_date), 'YYYYMMDD')
                    ORDER BY ls.created_at, ls.id
                ) AS seq,
                s.source_type::text AS source_category,
                s.name AS source_name
            FROM lead_signals ls
            LEFT JOIN sources s ON s.id = ls.source_id
        )
        UPDATE lead_signals ls
        SET
            lead_reference_id = 'MCA-' || n.scope || '-' || n.date_key || '-'
                || lpad(n.seq::text, 6, '0'),
            batch_number = 'BATCH-' || n.scope || '-' || n.date_key || '-001',
            batch_date = to_date(n.date_key, 'YYYYMMDD'),
            source_category = n.source_category,
            source_name = n.source_name,
            source_captured_at = coalesce(ls.created_at, now())
        FROM numbered n
        WHERE ls.id = n.id
        """
    )


def _backfill_ingestion_runs() -> None:
    op.execute(
        """
        WITH numbered AS (
            SELECT
                ir.id,
                upper(coalesce(s.state, 'ALL')) AS scope,
                to_char(coalesce(ir.started_at::date, current_date), 'YYYYMMDD') AS date_key,
                row_number() OVER (
                    PARTITION BY upper(coalesce(s.state, 'ALL')),
                    to_char(coalesce(ir.started_at::date, current_date), 'YYYYMMDD')
                    ORDER BY ir.started_at, ir.id
                ) AS seq,
                s.name AS source_name
            FROM ingestion_runs ir
            LEFT JOIN sources s ON s.id = ir.source_id
        )
        UPDATE ingestion_runs ir
        SET
            batch_number = 'BATCH-' || n.scope || '-' || n.date_key || '-'
                || lpad(n.seq::text, 3, '0'),
            batch_date = to_date(n.date_key, 'YYYYMMDD'),
            import_mode = coalesce(ir.run_type, 'unknown'),
            adapter_name = n.source_name,
            operator = 'migration'
        FROM numbered n
        WHERE ir.id = n.id
        """
    )


def _backfill_form_leads() -> None:
    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                to_char(coalesce(created_at::date, current_date), 'YYYYMMDD') AS date_key,
                row_number() OVER (
                    PARTITION BY to_char(coalesce(created_at::date, current_date), 'YYYYMMDD')
                    ORDER BY created_at, id
                ) AS seq
            FROM form_leads
        )
        UPDATE form_leads fl
        SET
            form_lead_ref_id = 'FORM-MCA-' || n.date_key || '-' || lpad(n.seq::text, 6, '0'),
            batch_number = 'BATCH-FORM-' || n.date_key || '-001'
        FROM numbered n
        WHERE fl.id = n.id
        """
    )


def _backfill_lead_deliveries() -> None:
    op.execute(
        """
        WITH numbered AS (
            SELECT
                ld.id,
                to_char(coalesce(ld.delivered_at::date, current_date), 'YYYYMMDD') AS date_key,
                row_number() OVER (
                    PARTITION BY to_char(coalesce(ld.delivered_at::date, current_date), 'YYYYMMDD')
                    ORDER BY ld.delivered_at, ld.id
                ) AS seq,
                ls.batch_number
            FROM lead_deliveries ld
            LEFT JOIN lead_signals ls ON ls.id = ld.lead_signal_id
        )
        UPDATE lead_deliveries ld
        SET
            delivery_id = 'DLV-' || n.date_key || '-' || lpad(n.seq::text, 6, '0'),
            batch_number = n.batch_number
        FROM numbered n
        WHERE ld.id = n.id
        """
    )


def _backfill_sequence_table() -> None:
    op.execute(
        """
        INSERT INTO id_sequences (sequence_type, scope, date_key, current_value)
        SELECT 'lead_reference', state,
            to_char(coalesce(created_at::date, signal_date), 'YYYYMMDD'),
            count(*)::integer
        FROM lead_signals
        GROUP BY state, to_char(coalesce(created_at::date, signal_date), 'YYYYMMDD')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO id_sequences (sequence_type, scope, date_key, current_value)
        SELECT 'batch', upper(coalesce(s.state, 'ALL')),
            to_char(coalesce(ir.started_at::date, current_date), 'YYYYMMDD'), count(*)::integer
        FROM ingestion_runs ir
        LEFT JOIN sources s ON s.id = ir.source_id
        GROUP BY upper(coalesce(s.state, 'ALL')),
            to_char(coalesce(ir.started_at::date, current_date), 'YYYYMMDD')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO id_sequences (sequence_type, scope, date_key, current_value)
        SELECT 'form_lead', 'MCA', to_char(coalesce(created_at::date, current_date), 'YYYYMMDD'),
            count(*)::integer
        FROM form_leads
        GROUP BY to_char(coalesce(created_at::date, current_date), 'YYYYMMDD')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO id_sequences (sequence_type, scope, date_key, current_value)
        SELECT 'delivery', 'ALL', to_char(coalesce(delivered_at::date, current_date), 'YYYYMMDD'),
            count(*)::integer
        FROM lead_deliveries
        GROUP BY to_char(coalesce(delivered_at::date, current_date), 'YYYYMMDD')
        ON CONFLICT DO NOTHING
        """
    )
