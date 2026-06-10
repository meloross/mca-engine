from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from app.integrations.google_sheets.client import GoogleSheetsClient
from app.integrations.google_sheets.mappers import (
    NO_CONSENT_REDACTION,
    map_delivery_to_delivery_log_row,
    map_form_lead_to_opt_in_row,
    map_ingestion_run_to_batch_log_row,
    map_lead_signal_to_master_row,
    map_source_to_source_registry_row,
)
from app.integrations.google_sheets.sync_service import LEAD_MASTER_TAB, GoogleSheetsSyncService
from app.models import (
    AccessMethod,
    BuyerAccount,
    DeliveryMethod,
    FormLead,
    IngestionRun,
    LeadDelivery,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    Source,
    SourceType,
)


def test_google_sheet_mappers_match_column_counts() -> None:
    source = _source()
    signal = _signal(source)
    run = _ingestion_run(source)
    buyer = _buyer()
    delivery = _delivery(signal, buyer)
    form_lead = _form_lead(consent_to_contact=True)
    _set_sheet_attr(run, "source", source)
    _set_sheet_attr(signal, "keyword_hits", ["merchant cash advance"])
    _set_sheet_attr(delivery, "lead", signal)
    _set_sheet_attr(delivery, "buyer", buyer)
    _set_sheet_attr(form_lead, "consented_at", datetime(2026, 6, 10, tzinfo=UTC))

    assert len(map_lead_signal_to_master_row(signal)) == 42
    assert len(map_ingestion_run_to_batch_log_row(run)) == 20
    assert len(map_source_to_source_registry_row(source)) == 13
    assert len(map_delivery_to_delivery_log_row(delivery)) == 13
    assert len(map_form_lead_to_opt_in_row(form_lead)) == 31


def test_no_consent_opt_in_mapper_redacts_contact_fields() -> None:
    form_lead = _form_lead(consent_to_contact=False)
    row = map_form_lead_to_opt_in_row(form_lead)

    assert row[5] == NO_CONSENT_REDACTION
    assert row[6] == NO_CONSENT_REDACTION
    assert row[7] == NO_CONSENT_REDACTION
    assert row[23] == NO_CONSENT_REDACTION


def test_disabled_sync_does_not_call_google_api() -> None:
    signal = _signal(_source())
    client = _FakeSheetsClient(enabled=False)
    service = GoogleSheetsSyncService(
        cast(Session, _FakeSyncSession()),
        client=cast(GoogleSheetsClient, client),
    )

    result = service._append_missing(
        tab_name=LEAD_MASTER_TAB,
        records=[signal],
        key_getter=lambda item: item.lead_reference_id,
        mapper=map_lead_signal_to_master_row,
        mark_synced=service._mark_signal_synced,
    )

    assert not result.enabled
    assert client.get_calls == 0
    assert client.append_calls == 0
    assert not signal.exported_to_master_sheet


def test_duplicate_lead_reference_is_not_appended_twice() -> None:
    signal = _signal(_source())
    client = _FakeSheetsClient(existing=[signal.lead_reference_id])
    service = GoogleSheetsSyncService(
        cast(Session, _FakeSyncSession()),
        client=cast(GoogleSheetsClient, client),
    )

    result = service._append_missing(
        tab_name=LEAD_MASTER_TAB,
        records=[signal],
        key_getter=lambda item: item.lead_reference_id,
        mapper=map_lead_signal_to_master_row,
        mark_synced=service._mark_signal_synced,
    )

    assert result.appended == 0
    assert result.skipped_duplicates == 1
    assert client.append_calls == 0
    assert not signal.exported_to_master_sheet


def test_failed_sync_does_not_mark_exported() -> None:
    signal = _signal(_source())
    session = _FakeSyncSession()
    client = _FakeSheetsClient(fail_append=True)
    service = GoogleSheetsSyncService(
        cast(Session, session),
        client=cast(GoogleSheetsClient, client),
    )

    result = service._append_missing(
        tab_name=LEAD_MASTER_TAB,
        records=[signal],
        key_getter=lambda item: item.lead_reference_id,
        mapper=map_lead_signal_to_master_row,
        mark_synced=service._mark_signal_synced,
    )

    assert result.error == "append failed"
    assert session.rollback_called
    assert not signal.exported_to_master_sheet


def test_successful_sync_marks_exported() -> None:
    signal = _signal(_source())
    session = _FakeSyncSession()
    client = _FakeSheetsClient(existing=["Lead Reference ID"])
    service = GoogleSheetsSyncService(
        cast(Session, session),
        client=cast(GoogleSheetsClient, client),
    )

    result = service._append_missing(
        tab_name=LEAD_MASTER_TAB,
        records=[signal],
        key_getter=lambda item: item.lead_reference_id,
        mapper=map_lead_signal_to_master_row,
        mark_synced=service._mark_signal_synced,
    )

    assert result.appended == 1
    assert signal.exported_to_master_sheet
    assert signal.master_sheet_row_number == 2
    assert signal.master_sheet_synced_at is not None


def _source() -> Source:
    return Source(
        id=uuid4(),
        name="NY Demo Source",
        state="NY",
        source_type=SourceType.COURT_NEW_CASES,
        base_url="https://example.com/source",
        access_method=AccessMethod.MOCK,
        terms_notes="Mock source.",
        automation_allowed=True,
        requires_login=False,
        requires_payment=False,
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
        updated_at=datetime(2026, 6, 10, tzinfo=UTC),
    )


def _signal(source: Source) -> LeadSignal:
    return LeadSignal(
        id=uuid4(),
        lead_reference_id="MCA-NY-20260610-000001",
        batch_number="BATCH-NY-20260610-001",
        batch_date=date(2026, 6, 10),
        source_category=source.source_type.value,
        source_name=source.name,
        source_captured_at=datetime(2026, 6, 10, tzinfo=UTC),
        signal_type=SignalType.LITIGATION_NEW_CASE,
        state="NY",
        county="Kings",
        business_name="Demo Merchant LLC",
        normalized_business_name="DEMO MERCHANT",
        funder_name="Cloudfund",
        signal_date=date(2026, 6, 10),
        title="Demo signal",
        summary="Merchant cash advance default.",
        score=95,
        risk_score=10,
        grade=LeadSignalGrade.A_PLUS,
        status=LeadSignalStatus.NEW,
        compliance_flags=["mock"],
        source_id=source.id,
        source_url="https://example.com/source/case",
        exported_to_master_sheet=False,
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
        updated_at=datetime(2026, 6, 10, tzinfo=UTC),
    )


def _ingestion_run(source: Source) -> IngestionRun:
    return IngestionRun(
        id=uuid4(),
        source_id=source.id,
        batch_number="BATCH-NY-20260610-001",
        batch_date=date(2026, 6, 10),
        import_mode="mock",
        adapter_name=source.name,
        query_filter_used="mock import",
        raw_artifact_path="data/artifacts/mock.html",
        raw_artifact_hash="0" * 64,
        operator="pytest",
        run_type="mock",
        status="completed",
        records_seen=10,
        records_created=10,
        records_updated=0,
        errors_count=0,
        started_at=datetime(2026, 6, 10, tzinfo=UTC),
        finished_at=datetime(2026, 6, 10, tzinfo=UTC),
    )


def _buyer() -> BuyerAccount:
    return BuyerAccount(
        id=uuid4(),
        firm_name="Demo Defense LLP",
        contact_name="Avery Buyer",
        email="buyer@example.com",
        phone="555-0100",
        states=["NY"],
        counties=["Kings"],
        practice_tags=["mca_defense"],
        active=True,
    )


def _delivery(signal: LeadSignal, buyer: BuyerAccount) -> LeadDelivery:
    return LeadDelivery(
        id=uuid4(),
        delivery_id="DLV-20260610-000001",
        batch_number=signal.batch_number,
        lead_signal_id=signal.id,
        buyer_account_id=buyer.id,
        delivery_method=DeliveryMethod.DASHBOARD,
        delivered_at=datetime(2026, 6, 10, tzinfo=UTC),
        accepted=True,
    )


def _form_lead(*, consent_to_contact: bool) -> FormLead:
    return FormLead(
        id=uuid4(),
        form_lead_ref_id="FORM-MCA-20260610-000001",
        linked_lead_reference_id="MCA-NY-20260610-000001",
        batch_number="BATCH-FORM-20260610-001",
        state="NY",
        business_name="Opt In Merchant LLC",
        contact_name="Riley Contact",
        email="riley@example.com",
        phone="555-0199",
        preferred_contact_method="email",
        legal_issue_type="mca_defense",
        has_been_sued=True,
        case_state="NY",
        case_county="Kings",
        case_number="2026-CV-100",
        mca_funder_names=["Cloudfund"],
        daily_weekly_payment_amount=Decimal("1500.00"),
        total_mca_balance_range="over $50k",
        bank_account_frozen=True,
        ucc_lien_issue=True,
        court_deadline_date=date(2026, 6, 15),
        has_attorney=False,
        consent_to_contact=consent_to_contact,
        consent_text="I agree to be contacted.",
        disclaimer_text="No legal advice.",
        page_url="https://example.com/lead-form",
        ip_hash="0" * 64,
        user_agent="pytest",
        source_campaign="test",
        score=90,
        grade=LeadSignalGrade.A_PLUS if consent_to_contact else LeadSignalGrade.EXCLUDE,
        status="new" if consent_to_contact else "excluded",
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
    )


class _FakeSheetsClient:
    def __init__(
        self,
        *,
        enabled: bool = True,
        existing: list[str] | None = None,
        fail_append: bool = False,
    ) -> None:
        self.enabled = enabled
        self.spreadsheet_id = "sheet-id"
        self.existing = existing or []
        self.fail_append = fail_append
        self.get_calls = 0
        self.append_calls = 0

    def get_column_values(self, tab_name: str, column: str = "A") -> list[str]:
        self.get_calls += 1
        return list(self.existing)

    def append_rows(self, tab_name: str, rows: list[list[str]]) -> dict[str, object]:
        self.append_calls += 1
        if self.fail_append:
            raise RuntimeError("append failed")
        self.existing.extend(row[0] for row in rows)
        return {"updates": {"updatedRows": len(rows)}}


def _set_sheet_attr(record: object, name: str, value: object) -> None:
    setattr(record, f"_sheet_{name}", value)


class _FakeSyncSession:
    def __init__(self) -> None:
        self.rollback_called = False
        self.commit_called = False
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commit_called = True

    def rollback(self) -> None:
        self.rollback_called = True
