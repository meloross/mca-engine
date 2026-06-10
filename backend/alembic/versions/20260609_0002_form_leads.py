"""Add opt-in MCA defense form leads.

Revision ID: 20260609_0002
Revises: 20260609_0001
Create Date: 2026-06-09 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260609_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


lead_signal_grade = postgresql.ENUM(
    "A_PLUS",
    "A",
    "B",
    "C",
    "D",
    "EXCLUDE",
    name="lead_signal_grade",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "form_leads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("business_name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("preferred_contact_method", sa.String(length=40), nullable=False),
        sa.Column("legal_issue_type", sa.String(length=120), nullable=False),
        sa.Column("has_been_sued", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("case_state", sa.String(length=2), nullable=True),
        sa.Column("case_county", sa.String(length=120), nullable=True),
        sa.Column("case_number", sa.String(length=120), nullable=True),
        sa.Column("mca_funder_names", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("daily_weekly_payment_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_mca_balance_range", sa.String(length=120), nullable=True),
        sa.Column("bank_account_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ucc_lien_issue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("court_deadline_date", sa.Date(), nullable=True),
        sa.Column("has_attorney", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_to_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("disclaimer_text", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("source_campaign", sa.String(length=255), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grade", lead_signal_grade, nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="new"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("form_leads")
