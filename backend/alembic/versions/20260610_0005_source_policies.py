"""Add source policies for live acquisition gating.

Revision ID: 20260610_0005
Revises: 20260610_0004
Create Date: 2026-06-10 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260610_0005"
down_revision = "20260610_0004"
branch_labels = None
depends_on = None


source_policy_source_type = postgresql.ENUM(
    "business_registry",
    "ucc_registry",
    "court_public_search",
    "court_login_portal",
    "county_clerk",
    "licensed_feed",
    "official_bulk_download",
    "enrichment",
    name="source_policy_source_type",
    create_type=False,
)
acquisition_method = postgresql.ENUM(
    "official_download",
    "public_search",
    "api",
    "playwright_public_search",
    "licensed_feed",
    "manual_import",
    "disabled",
    name="acquisition_method",
    create_type=False,
)
source_policy_status = postgresql.ENUM(
    "active",
    "disabled",
    "blocked_by_terms",
    "needs_permission",
    "error",
    name="source_policy_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    source_policy_source_type.create(bind, checkfirst=True)
    acquisition_method.create(bind, checkfirst=True)
    source_policy_status.create(bind, checkfirst=True)

    source_policies = op.create_table(
        "source_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_code", sa.String(120), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("source_type", source_policy_source_type, nullable=False),
        sa.Column("acquisition_method", acquisition_method, nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("robots_url", sa.Text(), nullable=True),
        sa.Column("automation_allowed", sa.Boolean(), nullable=True),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_login", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("captcha_observed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rate_limit_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_pages_per_run", sa.Integer(), nullable=False, server_default="25"),
        sa.Column(
            "status",
            source_policy_status,
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
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
        "uq_source_policies_source_code",
        "source_policies",
        ["source_code"],
        unique=True,
    )
    op.bulk_insert(
        source_policies,
        [
            {
                "source_code": "FL_SUNBIZ_DOWNLOADS",
                "source_name": "Florida Division of Corporations Data Downloads",
                "state": "FL",
                "source_type": "official_bulk_download",
                "acquisition_method": "official_download",
                "base_url": "https://dos.fl.gov/sunbiz/other-services/data-downloads/",
                "terms_url": "https://dos.fl.gov/sunbiz/other-services/data-downloads/",
                "robots_url": "https://dos.fl.gov/robots.txt",
                "automation_allowed": True,
                "live_enabled": True,
                "status": "active",
                "status_reason": "Official Sunbiz bulk download source.",
            },
            {
                "source_code": "FL_UCC_REGISTRY",
                "source_name": "Florida Secured Transaction Registry",
                "state": "FL",
                "source_type": "ucc_registry",
                "acquisition_method": "public_search",
                "base_url": "https://floridaucc.com/",
                "terms_url": "https://dos.fl.gov/sunbiz/other-services/ucc-information/",
                "robots_url": "https://floridaucc.com/robots.txt",
                "automation_allowed": None,
                "live_enabled": False,
                "status": "needs_permission",
                "status_reason": "Automation requires source-policy review.",
            },
            {
                "source_code": "NY_UCC_SEARCH",
                "source_name": "New York UCC Search",
                "state": "NY",
                "source_type": "ucc_registry",
                "acquisition_method": "public_search",
                "base_url": "https://dos.ny.gov/uniform-commercial-code",
                "terms_url": "https://dos.ny.gov/uniform-commercial-code",
                "robots_url": "https://dos.ny.gov/robots.txt",
                "automation_allowed": None,
                "live_enabled": False,
                "status": "needs_permission",
                "status_reason": "Automation requires source-policy review.",
            },
            {
                "source_code": "NY_UCC_DATA_DOWNLOAD",
                "source_name": "New York UCC Authorized Data Download",
                "state": "NY",
                "source_type": "licensed_feed",
                "acquisition_method": "licensed_feed",
                "base_url": "https://dos.ny.gov/uniform-commercial-code",
                "terms_url": "https://dos.ny.gov/uniform-commercial-code",
                "robots_url": "https://dos.ny.gov/robots.txt",
                "automation_allowed": None,
                "live_enabled": False,
                "requires_login": True,
                "status": "needs_permission",
                "status_reason": "Placeholder for authorized/licensed feed only.",
            },
            {
                "source_code": "NY_NYSCEF",
                "source_name": "NYSCEF Court Records",
                "state": "NY",
                "source_type": "court_login_portal",
                "acquisition_method": "disabled",
                "base_url": "https://iapps.courts.state.ny.us/nyscef/",
                "terms_url": "https://iapps.courts.state.ny.us/nyscef/",
                "robots_url": "https://iapps.courts.state.ny.us/robots.txt",
                "automation_allowed": False,
                "live_enabled": False,
                "requires_login": False,
                "status": "blocked_by_terms",
                "status_reason": (
                    "Do not automate NYSCEF in this product; use manual import "
                    "or authorized access."
                ),
            },
            {
                "source_code": "FL_EFILING_PORTAL",
                "source_name": "Florida E-Filing Portal",
                "state": "FL",
                "source_type": "court_login_portal",
                "acquisition_method": "disabled",
                "base_url": "https://myflcourtaccess.com/authority/",
                "terms_url": "https://myflcourtaccess.com/authority/",
                "robots_url": "https://myflcourtaccess.com/robots.txt",
                "automation_allowed": False,
                "live_enabled": False,
                "requires_login": True,
                "status": "blocked_by_terms",
                "status_reason": (
                    "Florida e-filing portal warning prohibits scraping/storing/"
                    "selling/reselling portal information."
                ),
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_source_policies_source_code", table_name="source_policies")
    op.drop_table("source_policies")
    source_policy_status.drop(op.get_bind(), checkfirst=True)
    acquisition_method.drop(op.get_bind(), checkfirst=True)
    source_policy_source_type.drop(op.get_bind(), checkfirst=True)
