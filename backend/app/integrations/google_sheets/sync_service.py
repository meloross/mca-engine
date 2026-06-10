from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.classifiers import classify_text
from app.integrations.google_sheets.client import GoogleSheetsClient
from app.integrations.google_sheets.mappers import (
    map_delivery_to_delivery_log_row,
    map_form_lead_to_opt_in_row,
    map_ingestion_run_to_batch_log_row,
    map_lead_signal_to_master_row,
    map_source_to_source_registry_row,
)
from app.integrations.google_sheets.schemas import GoogleSheetsSyncResult, GoogleSheetsSyncStatus
from app.models import (
    AuditLog,
    BuyerAccount,
    Case,
    CaseDocument,
    ConsentEvent,
    FormLead,
    IngestionRun,
    LeadDelivery,
    LeadSignal,
    Source,
    UccFiling,
)

LEAD_MASTER_TAB = "Lead_Master"
BATCH_LOG_TAB = "Batch_Log"
SOURCE_REGISTRY_TAB = "Source_Registry"
BUYER_DELIVERY_LOG_TAB = "Buyer_Delivery_Log"
OPT_IN_LEADS_TAB = "Opt_In_Leads"

RecordT = TypeVar("RecordT")


class GoogleSheetsSyncService:
    def __init__(
        self,
        session: Session,
        *,
        client: GoogleSheetsClient | None = None,
    ) -> None:
        self.session = session
        self.client = client or GoogleSheetsClient()

    def status(self) -> GoogleSheetsSyncStatus:
        return GoogleSheetsSyncStatus(
            enabled=self.client.enabled,
            spreadsheet_id=self.client.spreadsheet_id,
            unsynced_leads_count=self._count_unsynced_leads(),
            unsynced_batches_count=self._count_batches(),
            unsynced_deliveries_count=self._count_deliveries(),
            unsynced_opt_in_leads_count=self._count_unsynced_form_leads(),
            last_successful_sync=self._last_audit_created_at("google_sheets_sync_success"),
            last_error=self._last_error(),
        )

    def sync_new_leads_to_master_sheet(self, limit: int = 500) -> GoogleSheetsSyncResult:
        signals = list(
            self.session.scalars(
                select(LeadSignal)
                .where(LeadSignal.exported_to_master_sheet.is_(False))
                .order_by(LeadSignal.created_at.asc())
                .limit(limit)
            ).all()
        )
        for signal in signals:
            self._attach_lead_relations(signal)
        return self._append_missing(
            tab_name=LEAD_MASTER_TAB,
            records=signals,
            key_getter=lambda signal: signal.lead_reference_id,
            mapper=map_lead_signal_to_master_row,
            mark_synced=self._mark_signal_synced,
        )

    def sync_batch_log_to_master_sheet(self, limit: int = 100) -> GoogleSheetsSyncResult:
        runs = list(
            self.session.scalars(
                select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
            ).all()
        )
        for run in runs:
            _set_sheet_attr(run, "source", self.session.get(Source, run.source_id))
        return self._append_missing(
            tab_name=BATCH_LOG_TAB,
            records=runs,
            key_getter=lambda run: run.batch_number,
            mapper=map_ingestion_run_to_batch_log_row,
            mark_synced=lambda _run, _row, _synced_at: None,
        )

    def sync_sources_to_master_sheet(self) -> GoogleSheetsSyncResult:
        statement = select(Source).order_by(Source.state, Source.name)
        sources = list(self.session.scalars(statement).all())
        return self._append_missing(
            tab_name=SOURCE_REGISTRY_TAB,
            records=sources,
            key_getter=lambda source: str(source.id),
            mapper=map_source_to_source_registry_row,
            mark_synced=lambda _source, _row, _synced_at: None,
        )

    def sync_delivery_log_to_master_sheet(self, limit: int = 500) -> GoogleSheetsSyncResult:
        deliveries = list(
            self.session.scalars(
                select(LeadDelivery).order_by(LeadDelivery.delivered_at.asc()).limit(limit)
            ).all()
        )
        for delivery in deliveries:
            lead = self.session.get(LeadSignal, delivery.lead_signal_id)
            buyer = self.session.get(BuyerAccount, delivery.buyer_account_id)
            _set_sheet_attr(delivery, "lead", lead)
            _set_sheet_attr(delivery, "buyer", buyer)
        return self._append_missing(
            tab_name=BUYER_DELIVERY_LOG_TAB,
            records=deliveries,
            key_getter=lambda delivery: delivery.delivery_id,
            mapper=map_delivery_to_delivery_log_row,
            mark_synced=lambda _delivery, _row, _synced_at: None,
        )

    def sync_opt_in_leads_to_master_sheet(self, limit: int = 500) -> GoogleSheetsSyncResult:
        form_leads = list(
            self.session.scalars(
                select(FormLead)
                .where(FormLead.exported_to_master_sheet.is_(False))
                .order_by(FormLead.created_at.asc())
                .limit(limit)
            ).all()
        )
        for form_lead in form_leads:
            self._attach_form_lead_relations(form_lead)
        return self._append_missing(
            tab_name=OPT_IN_LEADS_TAB,
            records=form_leads,
            key_getter=lambda form_lead: form_lead.form_lead_ref_id,
            mapper=map_form_lead_to_opt_in_row,
            mark_synced=self._mark_form_lead_synced,
        )

    def sync_all_to_master_sheet(self) -> dict[str, GoogleSheetsSyncResult]:
        results = {
            "leads": self.sync_new_leads_to_master_sheet(),
            "batches": self.sync_batch_log_to_master_sheet(),
            "sources": self.sync_sources_to_master_sheet(),
            "deliveries": self.sync_delivery_log_to_master_sheet(),
            "opt_in_leads": self.sync_opt_in_leads_to_master_sheet(),
        }
        return results

    def _append_missing(
        self,
        *,
        tab_name: str,
        records: Sequence[RecordT],
        key_getter: Callable[[RecordT], str],
        mapper: Callable[[RecordT], list[str]],
        mark_synced: Callable[[RecordT, int, datetime], None],
    ) -> GoogleSheetsSyncResult:
        if not self.client.enabled:
            return GoogleSheetsSyncResult(
                tab_name=tab_name,
                enabled=False,
                attempted=len(records),
            )

        try:
            existing_keys = set(self.client.get_column_values(tab_name, "A"))
            pending = [record for record in records if key_getter(record) not in existing_keys]
            rows = [mapper(record) for record in pending]
            first_new_row = len(existing_keys) + 1
            if rows:
                self.client.append_rows(tab_name, rows)
                synced_at = datetime.now(UTC)
                for offset, record in enumerate(pending):
                    mark_synced(record, first_new_row + offset, synced_at)
                self._log_success(tab_name, len(rows))
                self.session.commit()
            return GoogleSheetsSyncResult(
                tab_name=tab_name,
                enabled=True,
                attempted=len(records),
                appended=len(rows),
                skipped_duplicates=len(records) - len(pending),
                row_numbers={
                    key_getter(record): first_new_row + offset
                    for offset, record in enumerate(pending)
                },
            )
        except Exception as exc:
            self.session.rollback()
            self._log_error(tab_name, str(exc))
            self.session.commit()
            return GoogleSheetsSyncResult(
                tab_name=tab_name,
                enabled=True,
                attempted=len(records),
                error=str(exc),
            )

    def _attach_lead_relations(self, signal: LeadSignal) -> None:
        case = self.session.get(Case, signal.case_id) if signal.case_id else None
        ucc = self.session.get(UccFiling, signal.ucc_filing_id) if signal.ucc_filing_id else None
        delivery = self.session.scalar(
            select(LeadDelivery)
            .where(LeadDelivery.lead_signal_id == signal.id)
            .order_by(LeadDelivery.delivered_at.desc())
        )
        buyer = self.session.get(BuyerAccount, delivery.buyer_account_id) if delivery else None
        _set_sheet_attr(signal, "case", case)
        _set_sheet_attr(signal, "ucc", ucc)
        _set_sheet_attr(signal, "delivery", delivery)
        _set_sheet_attr(signal, "buyer", buyer)
        _set_sheet_attr(signal, "keyword_hits", self._keyword_hits(case, ucc))

    def _attach_form_lead_relations(self, form_lead: FormLead) -> None:
        consent_event = self.session.scalar(
            select(ConsentEvent)
            .where(ConsentEvent.form_lead_id == str(form_lead.id))
            .order_by(ConsentEvent.consented_at.desc())
        )
        consented_at = consent_event.consented_at if consent_event else None
        _set_sheet_attr(form_lead, "consented_at", consented_at)

    def _keyword_hits(self, case: Case | None, ucc: UccFiling | None) -> list[str]:
        if case:
            hits: list[str] = []
            for document in self.session.scalars(
                select(CaseDocument).where(CaseDocument.case_id == case.id)
            ):
                hits.extend(document.keyword_hits)
            return list(dict.fromkeys(hits))
        if ucc:
            return list(classify_text(ucc.collateral_text).keyword_hits)
        return []

    def _mark_signal_synced(
        self,
        signal: LeadSignal,
        row_number: int,
        synced_at: datetime,
    ) -> None:
        signal.exported_to_master_sheet = True
        signal.master_sheet_row_number = row_number
        signal.master_sheet_synced_at = synced_at
        self.session.add(signal)

    def _mark_form_lead_synced(
        self,
        form_lead: FormLead,
        row_number: int,
        synced_at: datetime,
    ) -> None:
        form_lead.exported_to_master_sheet = True
        form_lead.master_sheet_row_number = row_number
        form_lead.master_sheet_synced_at = synced_at
        self.session.add(form_lead)

    def _log_success(self, tab_name: str, rows: int) -> None:
        self.session.add(
            AuditLog(
                actor="system",
                action="google_sheets_sync_success",
                entity_type="google_sheet",
                entity_id=tab_name,
                event_metadata={"rows": rows, "spreadsheet_id": self.client.spreadsheet_id},
            )
        )

    def _log_error(self, tab_name: str, error: str) -> None:
        self.session.add(
            AuditLog(
                actor="system",
                action="google_sheets_sync_error",
                entity_type="google_sheet",
                entity_id=tab_name,
                event_metadata={"error": error, "spreadsheet_id": self.client.spreadsheet_id},
            )
        )

    def _count_unsynced_leads(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(LeadSignal)
                .where(LeadSignal.exported_to_master_sheet.is_(False))
            )
            or 0
        )

    def _count_unsynced_form_leads(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(FormLead)
                .where(FormLead.exported_to_master_sheet.is_(False))
            )
            or 0
        )

    def _count_batches(self) -> int:
        return self.session.scalar(select(func.count()).select_from(IngestionRun)) or 0

    def _count_deliveries(self) -> int:
        return self.session.scalar(select(func.count()).select_from(LeadDelivery)) or 0

    def _last_audit_created_at(self, action: str) -> str | None:
        event = self.session.scalar(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
        )
        return event.created_at.isoformat() if event and event.created_at else None

    def _last_error(self) -> str | None:
        event = self.session.scalar(
            select(AuditLog)
            .where(AuditLog.action == "google_sheets_sync_error")
            .order_by(AuditLog.created_at.desc())
        )
        if event is None:
            return None
        error = event.event_metadata.get("error")
        return str(error) if error else None


def _set_sheet_attr(record: object, name: str, value: object) -> None:
    setattr(record, f"_sheet_{name}", value)
