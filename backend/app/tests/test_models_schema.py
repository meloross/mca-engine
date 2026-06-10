from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Index
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base

EXPECTED_TABLES = {
    "sources",
    "ingestion_runs",
    "raw_artifacts",
    "cases",
    "case_documents",
    "ucc_filings",
    "business_entities",
    "mca_funders",
    "lead_signals",
    "buyer_accounts",
    "buyer_rules",
    "lead_deliveries",
    "form_leads",
    "suppression_list",
    "consent_events",
    "audit_log",
}


def test_all_requested_tables_are_mapped() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


def test_reserved_metadata_columns_are_present_in_database_schema() -> None:
    assert "metadata" in Base.metadata.tables["raw_artifacts"].c
    assert "metadata" in Base.metadata.tables["audit_log"].c


def test_postgres_specific_column_types_compile() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    cases_sql = str(CreateTable(Base.metadata.tables["cases"]).compile(dialect=dialect))
    artifacts_sql = str(CreateTable(Base.metadata.tables["raw_artifacts"]).compile(dialect=dialect))

    assert "TEXT[]" in cases_sql
    assert "JSONB" in artifacts_sql


def test_required_unique_indexes_exist() -> None:
    expected = {
        "cases": ("uq_cases_state_court_name_case_number", ("state", "court_name", "case_number")),
        "ucc_filings": ("uq_ucc_filings_state_filing_number", ("state", "filing_number")),
        "lead_signals": (
            "uq_lead_signals_signal_type_state_business_date_funder",
            ("signal_type", "state", "normalized_business_name", "signal_date", "funder_name"),
        ),
        "mca_funders": ("uq_mca_funders_normalized_name", ("normalized_name",)),
    }

    for table_name, (index_name, column_names) in expected.items():
        indexes = {
            str(index.name): tuple(column.name for column in index.columns)
            for index in Base.metadata.tables[table_name].indexes
            if isinstance(index, Index) and index.name is not None
        }
        assert indexes[index_name] == column_names
        assert next(
            index for index in Base.metadata.tables[table_name].indexes if index.name == index_name
        ).unique


def test_source_access_method_enum_values_match_contract() -> None:
    access_column = Base.metadata.tables["sources"].c.access_method
    access_type = cast(Any, access_column.type)

    assert set(access_type.enums) == {
        "mock",
        "manual_import",
        "live_if_allowed",
        "licensed_bulk",
    }
