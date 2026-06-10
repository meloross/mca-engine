"""Add enrichment, contacts, and continuous job metadata.

Revision ID: 20260610_0004
Revises: 20260610_0003
Create Date: 2026-06-10 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260610_0004"
down_revision = "20260610_0003"
branch_labels = None
depends_on = None


enrichment_status = postgresql.ENUM(
    "pending",
    "success",
    "partial",
    "failed",
    "skipped",
    name="enrichment_status",
    create_type=False,
)
lead_contact_type = postgresql.ENUM(
    "business_phone",
    "business_email",
    "website",
    "owner_principal",
    "registered_agent",
    "mailing_address",
    "physical_address",
    name="lead_contact_type",
    create_type=False,
)
contact_verification_status = postgresql.ENUM(
    "unverified",
    "verified",
    "invalid",
    "risky",
    "unknown",
    name="contact_verification_status",
    create_type=False,
)


def text_array() -> postgresql.ARRAY:
    return postgresql.ARRAY(sa.Text())


def upgrade() -> None:
    bind = op.get_bind()
    enrichment_status.create(bind, checkfirst=True)
    lead_contact_type.create(bind, checkfirst=True)
    contact_verification_status.create(bind, checkfirst=True)

    op.add_column("lead_signals", sa.Column("owner_principal_name", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("owner_principal_title", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("owner_source", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("registered_agent_name", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("business_phone", sa.String(80), nullable=True))
    op.add_column("lead_signals", sa.Column("phone_source", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("business_email", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("email_source", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("business_website", sa.Text(), nullable=True))
    op.add_column("lead_signals", sa.Column("google_place_id", sa.String(255), nullable=True))
    op.add_column("lead_signals", sa.Column("google_maps_url", sa.Text(), nullable=True))
    op.add_column(
        "lead_signals",
        sa.Column(
            "enrichment_status",
            enrichment_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("lead_signals", sa.Column("enrichment_confidence", sa.Integer(), nullable=True))
    op.add_column(
        "lead_signals",
        sa.Column(
            "enrichment_sources",
            text_array(),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )
    op.add_column(
        "lead_signals",
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lead_signals",
        sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "business_enrichments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("lead_signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_reference_id", sa.String(40), nullable=False),
        sa.Column("normalized_business_name", sa.Text(), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("county", sa.String(120), nullable=True),
        sa.Column("source_provider", sa.String(120), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=True),
        sa.Column("google_place_id", sa.String(255), nullable=True),
        sa.Column("google_maps_url", sa.Text(), nullable=True),
        sa.Column("business_website", sa.Text(), nullable=True),
        sa.Column("business_phone", sa.String(80), nullable=True),
        sa.Column("business_email", sa.Text(), nullable=True),
        sa.Column("owner_principal_name", sa.Text(), nullable=True),
        sa.Column("owner_principal_title", sa.Text(), nullable=True),
        sa.Column("registered_agent_name", sa.Text(), nullable=True),
        sa.Column("registered_agent_address", sa.Text(), nullable=True),
        sa.Column("business_address", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", enrichment_status, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("raw_response_path", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
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
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lead_signal_id"], ["lead_signals.id"]),
    )
    op.create_index(
        "ix_business_enrichments_lead_reference_id",
        "business_enrichments",
        ["lead_reference_id"],
    )

    op.create_table(
        "lead_contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("lead_signal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_reference_id", sa.String(40), nullable=False),
        sa.Column("contact_type", lead_contact_type, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("source_provider", sa.String(120), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_category", sa.String(120), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "verification_status",
            contact_verification_status,
            nullable=False,
            server_default="unverified",
        ),
        sa.Column("is_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contact_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contact_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "found_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["lead_signal_id"], ["lead_signals.id"]),
    )
    op.create_index("ix_lead_contacts_lead_reference_id", "lead_contacts", ["lead_reference_id"])
    op.create_index(
        "uq_lead_contacts_reference_type_value",
        "lead_contacts",
        ["lead_reference_id", "contact_type", "normalized_value"],
        unique=True,
    )

    op.create_table(
        "enrichment_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("enrichment_run_id", sa.String(80), nullable=False, unique=True),
        sa.Column("batch_number", sa.String(40), nullable=True),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_partial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "enrichment_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("enrichment_run_id", sa.String(80), nullable=False),
        sa.Column("lead_reference_id", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("enrichment_attempts")
    op.drop_table("enrichment_runs")
    op.drop_index("uq_lead_contacts_reference_type_value", table_name="lead_contacts")
    op.drop_index("ix_lead_contacts_lead_reference_id", table_name="lead_contacts")
    op.drop_table("lead_contacts")
    op.drop_index(
        "ix_business_enrichments_lead_reference_id",
        table_name="business_enrichments",
    )
    op.drop_table("business_enrichments")
    op.drop_column("lead_signals", "do_not_contact")
    op.drop_column("lead_signals", "enriched_at")
    op.drop_column("lead_signals", "enrichment_sources")
    op.drop_column("lead_signals", "enrichment_confidence")
    op.drop_column("lead_signals", "enrichment_status")
    op.drop_column("lead_signals", "google_maps_url")
    op.drop_column("lead_signals", "google_place_id")
    op.drop_column("lead_signals", "business_website")
    op.drop_column("lead_signals", "email_source")
    op.drop_column("lead_signals", "business_email")
    op.drop_column("lead_signals", "phone_source")
    op.drop_column("lead_signals", "business_phone")
    op.drop_column("lead_signals", "registered_agent_name")
    op.drop_column("lead_signals", "owner_source")
    op.drop_column("lead_signals", "owner_principal_title")
    op.drop_column("lead_signals", "owner_principal_name")
    contact_verification_status.drop(op.get_bind(), checkfirst=True)
    lead_contact_type.drop(op.get_bind(), checkfirst=True)
    enrichment_status.drop(op.get_bind(), checkfirst=True)
