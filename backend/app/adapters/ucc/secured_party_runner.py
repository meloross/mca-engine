from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ucc.base_ucc_live import BaseUccLiveAdapter, UccSearchRecord
from app.classifiers import classify_text
from app.compliance import normalize_business_name
from app.ids import next_batch_number, next_lead_reference_id
from app.models import (
    AccessMethod,
    AuditLog,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    Source,
    SourceType,
    UccFiling,
)
from app.scoring import score_signal


@dataclass(frozen=True)
class UccInsertResult:
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    leads_created: int = 0
    leads_updated: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = ()


def run_authorized_secured_party_queries(
    adapter: BaseUccLiveAdapter,
    secured_party_names: Iterable[str],
) -> list[UccSearchRecord]:
    records: list[UccSearchRecord] = []
    for name in secured_party_names:
        result = adapter.run_for_secured_party(name)
        if result.status == "ok":
            records.extend(result.records)
    return records


def upsert_ucc_records_as_signals(
    session: Session,
    records: list[UccSearchRecord],
    *,
    source: Source,
    dry_run: bool = False,
) -> UccInsertResult:
    created = 0
    updated = 0
    leads_created = 0
    leads_updated = 0
    skipped = 0
    errors: list[str] = []
    for record in records:
        if not record.filing_number.strip() or not record.debtor_name:
            skipped += 1
            continue
        try:
            if dry_run:
                continue
            ucc, was_created = _upsert_ucc(session, record, source=source)
            if was_created:
                created += 1
            else:
                updated += 1
            signal_created = _upsert_signal_for_ucc(session, ucc, source=source)
            if signal_created:
                leads_created += 1
            else:
                leads_updated += 1
        except Exception as exc:
            errors.append(f"{record.state} {record.filing_number}: {exc}")
    return UccInsertResult(
        records_seen=len(records),
        records_created=created,
        records_updated=updated,
        leads_created=leads_created,
        leads_updated=leads_updated,
        skipped=skipped,
        errors=tuple(errors),
    )


def source_for_live_policy(session: Session, *, name: str, state: str, base_url: str) -> Source:
    source = session.scalar(select(Source).where(Source.name == name, Source.state == state))
    if source is None:
        source = Source(
            name=name,
            state=state,
            source_type=SourceType.UCC_REGISTRY,
            base_url=base_url,
            access_method=AccessMethod.LIVE_IF_ALLOWED,
            terms_notes="Policy-gated live source. No CAPTCHA, login, or access-control bypass.",
            automation_allowed=True,
            requires_login=False,
            requires_payment=False,
        )
        session.add(source)
        session.flush()
    return source


def _upsert_ucc(
    session: Session,
    record: UccSearchRecord,
    *,
    source: Source,
) -> tuple[UccFiling, bool]:
    filing_number = record.filing_number.strip()
    ucc = session.scalar(
        select(UccFiling).where(
            UccFiling.state == record.state,
            UccFiling.filing_number == filing_number,
        )
    )
    was_created = ucc is None
    if ucc is None:
        ucc = UccFiling(
            state=record.state,
            filing_number=filing_number,
            source_id=source.id,
            source_url=record.source_url,
            normalized_key=f"{record.state}:UCC:{filing_number.upper()}",
        )
        session.add(ucc)
    ucc.filing_type = record.filing_type
    ucc.filing_date = record.filing_date
    ucc.debtor_name = record.debtor_name
    ucc.debtor_address = record.debtor_address
    ucc.secured_party_name = record.secured_party_name
    ucc.secured_party_address = record.secured_party_address
    ucc.collateral_text = record.collateral_text
    ucc.source_id = source.id
    ucc.source_url = record.source_url
    session.flush()
    return ucc, was_created


def _upsert_signal_for_ucc(session: Session, ucc: UccFiling, *, source: Source) -> bool:
    signal_date = ucc.filing_date or date.today()
    signal_type = _signal_type_for_filing(ucc.filing_type)
    normalized_name = normalize_business_name(ucc.debtor_name or ucc.filing_number)
    existing = session.scalar(
        select(LeadSignal).where(
            LeadSignal.signal_type == signal_type,
            LeadSignal.state == ucc.state,
            LeadSignal.normalized_business_name == normalized_name,
            LeadSignal.signal_date == signal_date,
            LeadSignal.funder_name == ucc.secured_party_name,
        )
    )
    score = score_signal(
        {
            "signal_type": signal_type.value,
            "business_name": ucc.debtor_name,
            "defendant_names": [ucc.debtor_name] if ucc.debtor_name else [],
            "funder_name": ucc.secured_party_name,
            "secured_party_name": ucc.secured_party_name,
            "collateral_text": ucc.collateral_text,
            "filing_date": signal_date,
            "source_automation_allowed": True,
            "merchant_business_defendant": True,
            "no_defense_attorney": True,
        },
        as_of=date.today(),
    )
    keywords = classify_text(ucc.collateral_text)
    compliance_flags = ["live_if_allowed", "ucc_public_record"]
    if score.excluded:
        compliance_flags.extend(score.exclusion_reasons)

    signal = existing
    created = signal is None
    if signal is None:
        signal = LeadSignal(
            lead_reference_id=next_lead_reference_id(session, ucc.state, signal_date),
            batch_number=next_batch_number(session, "LIVE", signal_date),
            batch_date=signal_date,
            signal_type=signal_type,
            state=ucc.state,
            business_name=ucc.debtor_name or ucc.filing_number,
            normalized_business_name=normalized_name,
            funder_name=ucc.secured_party_name,
            signal_date=signal_date,
            source_id=source.id,
            source_url=ucc.source_url,
            grade=LeadSignalGrade(score.grade),
            status=LeadSignalStatus.EXCLUDED if score.excluded else LeadSignalStatus.NEW,
            title=f"Live UCC signal: {ucc.debtor_name or ucc.filing_number}",
        )
        session.add(signal)
    signal.ucc_filing_id = ucc.id
    signal.score = score.score
    signal.risk_score = score.risk_score
    signal.grade = LeadSignalGrade(score.grade)
    signal.status = LeadSignalStatus.EXCLUDED if score.excluded else signal.status
    signal.exclusion_reason = "; ".join(score.exclusion_reasons) if score.excluded else None
    signal.summary = "MCA-related UCC record from policy-gated live source."
    signal.source_category = source.source_type.value
    signal.source_name = source.name
    signal.source_captured_at = datetime.now(UTC)
    signal.compliance_flags = list(dict.fromkeys((*compliance_flags, *keywords.keyword_hits)))
    session.add(
        AuditLog(
            actor="live_harvester",
            action="live_ucc_signal_upserted",
            entity_type="lead_signal",
            entity_id=signal.lead_reference_id,
            event_metadata={
                "ucc_filing_number": ucc.filing_number,
                "created": created,
                "score_reasons": list(score.reasons),
            },
        )
    )
    session.flush()
    return created


def _signal_type_for_filing(filing_type: str | None) -> SignalType:
    value = (filing_type or "").lower()
    if "termination" in value:
        return SignalType.UCC_TERMINATION
    if "continuation" in value:
        return SignalType.UCC_CONTINUATION
    if "assignment" in value:
        return SignalType.UCC_ASSIGNMENT
    if "amend" in value:
        return SignalType.UCC_AMENDMENT
    return SignalType.UCC_INITIAL
