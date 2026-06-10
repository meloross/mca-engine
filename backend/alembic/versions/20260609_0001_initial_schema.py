"""Initial MCA legal signal schema.

Revision ID: 20260609_0001
Revises:
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


source_type = sa.Enum(
    "court_new_cases",
    "court_case_search",
    "ucc_registry",
    "business_registry",
    "federal_bankruptcy",
    "manual_upload",
    name="source_type",
)
access_method = sa.Enum(
    "mock",
    "manual_import",
    "live_if_allowed",
    "licensed_bulk",
    name="access_method",
)
artifact_type = sa.Enum(
    "html",
    "pdf",
    "csv",
    "json",
    "txt",
    "screenshot",
    "manual",
    name="artifact_type",
)
signal_type = sa.Enum(
    "litigation_new_case",
    "litigation_update",
    "ucc_initial",
    "ucc_amendment",
    "ucc_assignment",
    "ucc_continuation",
    "ucc_termination",
    "bankruptcy_mca_creditor",
    "manual",
    name="signal_type",
)
lead_signal_grade = sa.Enum("A_PLUS", "A", "B", "C", "D", "EXCLUDE", name="lead_signal_grade")
lead_signal_status = sa.Enum(
    "new",
    "reviewed",
    "delivered",
    "suppressed",
    "excluded",
    name="lead_signal_status",
)
delivery_method = sa.Enum("dashboard", "email", "webhook", "csv", name="delivery_method")
suppression_type = sa.Enum(
    "business_name",
    "person_name",
    "phone",
    "email",
    "case_number",
    "domain",
    name="suppression_type",
)


def text_array() -> postgresql.ARRAY:
    return postgresql.ARRAY(sa.Text())


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("access_method", access_method, nullable=False),
        sa.Column("terms_notes", sa.Text(), nullable=True),
        sa.Column("automation_allowed", sa.Boolean(), nullable=True),
        sa.Column("requires_login", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
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

    op.create_table(
        "ingestion_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("run_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "raw_artifacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column(
            "ingestion_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_runs.id"),
            nullable=False,
        ),
        sa.Column("artifact_type", artifact_type, nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_table(
        "cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=True),
        sa.Column("court_name", sa.String(length=255), nullable=False),
        sa.Column("case_number", sa.String(length=120), nullable=False),
        sa.Column("case_type", sa.String(length=120), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("last_activity_date", sa.Date(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "plaintiff_names",
            text_array(),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "defendant_names",
            text_array(),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "attorney_names",
            text_array(),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "raw_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_artifacts.id"),
            nullable=True,
        ),
        sa.Column("normalized_key", sa.String(length=500), nullable=False),
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
        "uq_cases_state_court_name_case_number",
        "cases",
        ["state", "court_name", "case_number"],
        unique=True,
    )

    op.create_table(
        "case_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("document_type", sa.String(length=120), nullable=True),
        sa.Column("document_title", sa.Text(), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("has_mca_keywords", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "keyword_hits", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "ucc_filings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("filing_number", sa.String(length=120), nullable=False),
        sa.Column("filing_type", sa.String(length=120), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("lapse_date", sa.Date(), nullable=True),
        sa.Column("debtor_name", sa.Text(), nullable=True),
        sa.Column("debtor_address", sa.Text(), nullable=True),
        sa.Column("secured_party_name", sa.Text(), nullable=True),
        sa.Column("secured_party_address", sa.Text(), nullable=True),
        sa.Column("collateral_text", sa.Text(), nullable=True),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "raw_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_artifacts.id"),
            nullable=True,
        ),
        sa.Column("normalized_key", sa.String(length=500), nullable=False),
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
        "uq_ucc_filings_state_filing_number", "ucc_filings", ["state", "filing_number"], unique=True
    )

    op.create_table(
        "business_entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("entity_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("principal_address", sa.Text(), nullable=True),
        sa.Column("mailing_address", sa.Text(), nullable=True),
        sa.Column("registered_agent_name", sa.Text(), nullable=True),
        sa.Column("registered_agent_address", sa.Text(), nullable=True),
        sa.Column(
            "officers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "mca_funders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column(
            "aliases", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "uq_mca_funders_normalized_name", "mca_funders", ["normalized_name"], unique=True
    )

    op.create_table(
        "lead_signals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("signal_type", signal_type, nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=False),
        sa.Column("normalized_business_name", sa.Text(), nullable=False),
        sa.Column("funder_name", sa.Text(), nullable=True),
        sa.Column(
            "case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=True
        ),
        sa.Column(
            "ucc_filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ucc_filings.id"),
            nullable=True,
        ),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grade", lead_signal_grade, nullable=False),
        sa.Column("status", lead_signal_status, nullable=False, server_default="new"),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column(
            "compliance_flags",
            text_array(),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
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
        "uq_lead_signals_signal_type_state_business_date_funder",
        "lead_signals",
        ["signal_type", "state", "normalized_business_name", "signal_date", "funder_name"],
        unique=True,
    )

    op.create_table(
        "buyer_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("firm_name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column(
            "states", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column(
            "counties", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column(
            "practice_tags", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "buyer_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "buyer_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buyer_accounts.id"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column(
            "counties", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column("min_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "signal_types", text_array(), nullable=False, server_default=sa.text("ARRAY[]::text[]")
        ),
        sa.Column("exclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "lead_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_signal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_signals.id"),
            nullable=False,
        ),
        sa.Column(
            "buyer_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buyer_accounts.id"),
            nullable=False,
        ),
        sa.Column("delivery_method", delivery_method, nullable=False),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "suppression_list",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("suppression_type", suppression_type, nullable=False),
        sa.Column("value_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "consent_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_signal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_signals.id"),
            nullable=True,
        ),
        sa.Column("form_lead_id", sa.String(length=120), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("ip_address_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buyer_disclosure", sa.Text(), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("consent_events")
    op.drop_table("suppression_list")
    op.drop_table("lead_deliveries")
    op.drop_table("buyer_rules")
    op.drop_table("buyer_accounts")
    op.drop_index(
        "uq_lead_signals_signal_type_state_business_date_funder", table_name="lead_signals"
    )
    op.drop_table("lead_signals")
    op.drop_index("uq_mca_funders_normalized_name", table_name="mca_funders")
    op.drop_table("mca_funders")
    op.drop_table("business_entities")
    op.drop_index("uq_ucc_filings_state_filing_number", table_name="ucc_filings")
    op.drop_table("ucc_filings")
    op.drop_table("case_documents")
    op.drop_index("uq_cases_state_court_name_case_number", table_name="cases")
    op.drop_table("cases")
    op.drop_table("raw_artifacts")
    op.drop_table("ingestion_runs")
    op.drop_table("sources")

    suppression_type.drop(op.get_bind(), checkfirst=True)
    delivery_method.drop(op.get_bind(), checkfirst=True)
    lead_signal_status.drop(op.get_bind(), checkfirst=True)
    lead_signal_grade.drop(op.get_bind(), checkfirst=True)
    signal_type.drop(op.get_bind(), checkfirst=True)
    artifact_type.drop(op.get_bind(), checkfirst=True)
    access_method.drop(op.get_bind(), checkfirst=True)
    source_type.drop(op.get_bind(), checkfirst=True)
