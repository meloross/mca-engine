from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import NormalizedRecord
from app.adapters.new_york import NewYorkUccAdapter, NyscefNewCasesAdapter
from app.classifiers import classify_text
from app.compliance import normalize_business_name
from app.config import settings
from app.models import (
    AccessMethod,
    ArtifactType,
    AuditLog,
    Case,
    CaseDocument,
    IngestionRun,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    RawArtifact,
    SignalType,
    Source,
    SourceType,
    UccFiling,
)
from app.scoring import LeadScoreResult, score_signal
from app.services.presentation import document_datetime_from_date

MOCK_AS_OF_DATE = date(2026, 6, 9)


@dataclass(frozen=True)
class SignalPayload:
    record_type: str
    source_id: str
    source_url: str
    captured_at: datetime
    raw_artifact_path: str
    normalized_key: str
    signal: dict[str, Any]
    source_record: dict[str, Any]
    score_result: LeadScoreResult


async def build_mock_ny_signal_payloads(
    *,
    artifacts_dir: Path | str = "data/artifacts",
    source_ids: dict[str, str] | None = None,
) -> list[SignalPayload]:
    ids = source_ids or {"cases": "ny-nyscef-new-cases", "ucc": "ny-ucc-search"}
    normalized_records: list[NormalizedRecord] = []

    cases_adapter = NyscefNewCasesAdapter(
        mode="mock",
        source_id=ids["cases"],
        artifacts_dir=artifacts_dir,
        rate_limit_seconds=0,
    )
    ucc_adapter = NewYorkUccAdapter(
        mode="mock",
        source_id=ids["ucc"],
        artifacts_dir=artifacts_dir,
        rate_limit_seconds=0,
    )

    for adapter, params in (
        (cases_adapter, {"court_name": "ALL", "filing_date": "2026-06-09"}),
        (ucc_adapter, {"secured_party_name": "ALL"}),
    ):
        artifacts = await adapter.fetch(params)
        for artifact in artifacts:
            parsed_records = await adapter.parse(artifact)
            for parsed_record in parsed_records:
                normalized_records.append(await adapter.normalize(parsed_record))

    return [
        _normalized_to_signal_payload(record, as_of=MOCK_AS_OF_DATE)
        for record in normalized_records
    ]


async def import_mock_ny_to_db(session: Session) -> dict[str, int]:
    case_source = _get_or_create_source(
        session,
        name=NyscefNewCasesAdapter.source_name,
        state="NY",
        source_type=SourceType.COURT_NEW_CASES,
        base_url=NyscefNewCasesAdapter.base_url,
        terms_notes=NyscefNewCasesAdapter.terms_notes,
    )
    ucc_source = _get_or_create_source(
        session,
        name=NewYorkUccAdapter.source_name,
        state="NY",
        source_type=SourceType.UCC_REGISTRY,
        base_url=NewYorkUccAdapter.base_url,
        terms_notes=NewYorkUccAdapter.terms_notes,
    )
    session.flush()

    payloads = await build_mock_ny_signal_payloads(
        artifacts_dir=settings.artifact_storage_dir,
        source_ids={"cases": str(case_source.id), "ucc": str(ucc_source.id)},
    )
    runs = {
        str(case_source.id): _create_ingestion_run(session, case_source),
        str(ucc_source.id): _create_ingestion_run(session, ucc_source),
    }
    artifact_cache: dict[tuple[str, str], RawArtifact] = {}
    created_signals = 0
    updated_signals = 0

    for payload in payloads:
        source = case_source if payload.record_type == "case" else ucc_source
        artifact = _get_or_create_raw_artifact(
            session,
            artifact_path=payload.raw_artifact_path,
            source=source,
            run=runs[str(source.id)],
            source_url=payload.source_url,
            captured_at=payload.captured_at,
            cache=artifact_cache,
        )
        source_entity_id: UUID | None = None
        if payload.record_type == "case":
            source_entity_id = _upsert_case(session, payload, source, artifact)
        elif payload.record_type == "ucc_filing":
            source_entity_id = _upsert_ucc(session, payload, source, artifact)

        if _upsert_signal(session, payload, source, source_entity_id):
            created_signals += 1
        else:
            updated_signals += 1

    for run in runs.values():
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.records_seen = len(payloads)
        run.records_created = created_signals
        run.records_updated = updated_signals

    session.add(
        AuditLog(
            actor="system",
            action="admin_import_mock",
            entity_type="state",
            entity_id="NY",
            event_metadata={
                "signals_created": created_signals,
                "signals_updated": updated_signals,
                "records_seen": len(payloads),
            },
        )
    )
    session.commit()
    return {
        "records_seen": len(payloads),
        "signals_created": created_signals,
        "signals_updated": updated_signals,
    }


def _normalized_to_signal_payload(record: NormalizedRecord, *, as_of: date) -> SignalPayload:
    data = record.data
    score_result = score_signal(_scoring_record(record), as_of=as_of)
    business_name = _business_name(record)
    signal_date = _date_value(data.get("filing_date")) or as_of
    signal_type = _signal_type(record)

    return SignalPayload(
        record_type=record.record_type,
        source_id=record.source_id,
        source_url=record.source_url,
        captured_at=record.captured_at,
        raw_artifact_path=record.raw_artifact_path,
        normalized_key=record.normalized_key,
        source_record=data,
        score_result=score_result,
        signal={
            "signal_type": signal_type,
            "state": "NY",
            "county": data.get("county"),
            "business_name": business_name,
            "normalized_business_name": normalize_business_name(business_name),
            "funder_name": score_result.funder_match.matched_funder,
            "signal_date": signal_date,
            "title": _signal_title(record, business_name),
            "summary": _summary(record),
            "score": score_result.score,
            "risk_score": score_result.risk_score,
            "grade": score_result.grade,
            "status": "excluded" if score_result.excluded else "new",
            "exclusion_reason": "; ".join(score_result.exclusion_reasons) or None,
            "compliance_flags": list(score_result.exclusion_reasons),
            "source_url": record.source_url,
        },
    )


def _scoring_record(record: NormalizedRecord) -> dict[str, Any]:
    data = record.data
    if record.record_type == "case":
        return {
            "signal_type": "litigation_new_case",
            "caption": data.get("caption"),
            "plaintiff_names": data.get("plaintiff_names", []),
            "defendant_names": data.get("defendant_names", []),
            "document_text": data.get("document_text"),
            "filing_date": data.get("filing_date"),
            "defense_attorney_names": data.get("defense_attorney_names", []),
            "source_automation_allowed": True,
        }
    return {
        "signal_type": _signal_type(record),
        "ucc_secured_party": data.get("secured_party_name"),
        "secured_party_name": data.get("secured_party_name"),
        "debtor_name": data.get("debtor_name"),
        "defendant_names": [data.get("debtor_name")] if data.get("debtor_name") else [],
        "ucc_collateral_text": data.get("collateral_text"),
        "filing_date": data.get("filing_date"),
        "source_automation_allowed": True,
    }


def _signal_type(record: NormalizedRecord) -> str:
    if record.record_type == "case":
        return "litigation_new_case"

    filing_type = str(record.data.get("filing_type") or "").lower()
    if "assignment" in filing_type:
        return "ucc_assignment"
    if "continuation" in filing_type:
        return "ucc_continuation"
    if "termination" in filing_type:
        return "ucc_termination"
    if "amendment" in filing_type or "ucc-3" in filing_type:
        return "ucc_amendment"
    return "ucc_initial"


def _business_name(record: NormalizedRecord) -> str:
    if record.record_type == "case":
        defendants = record.data.get("defendant_names")
        if isinstance(defendants, list) and defendants:
            return str(defendants[0])
        return str(record.data.get("caption") or "Unknown NY defendant")
    return str(record.data.get("debtor_name") or "Unknown NY debtor")


def _signal_title(record: NormalizedRecord, business_name: str) -> str:
    if record.record_type == "case":
        return f"New NY MCA litigation signal: {business_name}"
    return f"NY UCC signal for {business_name} ({record.data.get('filing_number')})"


def _summary(record: NormalizedRecord) -> str:
    if record.record_type == "case":
        return str(record.data.get("caption") or record.data.get("document_text") or "")
    return str(record.data.get("collateral_text") or "")


def _date_value(value: object) -> date | None:
    return value if isinstance(value, date) and not isinstance(value, datetime) else None


def _get_or_create_source(
    session: Session,
    *,
    name: str,
    state: str,
    source_type: SourceType,
    base_url: str,
    terms_notes: str,
) -> Source:
    source = session.scalar(select(Source).where(Source.name == name, Source.state == state))
    if source is not None:
        return source

    source = Source(
        name=name,
        state=state,
        source_type=source_type,
        base_url=base_url,
        access_method=AccessMethod.MOCK,
        terms_notes=terms_notes,
        automation_allowed=None,
        requires_login=False,
        requires_payment=False,
    )
    session.add(source)
    return source


def _create_ingestion_run(session: Session, source: Source) -> IngestionRun:
    run = IngestionRun(
        source=source, run_type="mock", status="running", started_at=datetime.now(UTC)
    )
    session.add(run)
    session.flush()
    return run


def _get_or_create_raw_artifact(
    session: Session,
    *,
    artifact_path: str,
    source: Source,
    run: IngestionRun,
    source_url: str,
    captured_at: datetime,
    cache: dict[tuple[str, str], RawArtifact],
) -> RawArtifact:
    key = (str(source.id), artifact_path)
    if key in cache:
        return cache[key]

    artifact_type = _artifact_type_from_path(artifact_path)
    raw_artifact = RawArtifact(
        source=source,
        ingestion_run=run,
        artifact_type=artifact_type,
        storage_path=artifact_path,
        sha256_hash=_sha256_file(artifact_path),
        source_url=source_url,
        captured_at=captured_at,
        artifact_metadata={"access_method": "mock"},
    )
    session.add(raw_artifact)
    session.flush()
    cache[key] = raw_artifact
    return raw_artifact


def _upsert_case(
    session: Session,
    payload: SignalPayload,
    source: Source,
    artifact: RawArtifact,
) -> UUID:
    data = payload.source_record
    case = session.scalar(
        select(Case).where(
            Case.state == "NY",
            Case.court_name == data["court_name"],
            Case.case_number == data["case_number"],
        )
    )
    if case is None:
        case = Case(
            state="NY",
            county=data.get("county"),
            court_name=data["court_name"],
            case_number=data["case_number"],
            source_id=source.id,
            raw_artifact_id=artifact.id,
            normalized_key=payload.normalized_key,
            source_url=payload.source_url,
        )
        session.add(case)
    case.case_type = data.get("case_type")
    case.filing_date = data.get("filing_date")
    case.caption = data.get("caption")
    case.plaintiff_names = _string_list(data.get("plaintiff_names"))
    case.defendant_names = _string_list(data.get("defendant_names"))
    case.attorney_names = _string_list(data.get("attorney_names"))
    session.flush()
    _upsert_case_document(session, case, payload)
    return case.id


def _upsert_ucc(
    session: Session,
    payload: SignalPayload,
    source: Source,
    artifact: RawArtifact,
) -> UUID:
    data = payload.source_record
    ucc = session.scalar(
        select(UccFiling).where(
            UccFiling.state == "NY",
            UccFiling.filing_number == data["filing_number"],
        )
    )
    if ucc is None:
        ucc = UccFiling(
            state="NY",
            filing_number=data["filing_number"],
            source_id=source.id,
            raw_artifact_id=artifact.id,
            normalized_key=payload.normalized_key,
            source_url=payload.source_url,
        )
        session.add(ucc)
    ucc.filing_type = data.get("filing_type")
    ucc.filing_date = data.get("filing_date")
    ucc.debtor_name = data.get("debtor_name")
    ucc.debtor_address = data.get("debtor_address")
    ucc.secured_party_name = data.get("secured_party_name")
    ucc.secured_party_address = data.get("secured_party_address")
    ucc.collateral_text = data.get("collateral_text")
    session.flush()
    return ucc.id


def _upsert_signal(
    session: Session,
    payload: SignalPayload,
    source: Source,
    source_entity_id: UUID | None,
) -> bool:
    signal = payload.signal
    existing = session.scalar(
        select(LeadSignal).where(
            LeadSignal.signal_type == SignalType(signal["signal_type"]),
            LeadSignal.state == signal["state"],
            LeadSignal.normalized_business_name == signal["normalized_business_name"],
            LeadSignal.signal_date == signal["signal_date"],
            LeadSignal.funder_name == signal["funder_name"],
        )
    )
    created = existing is None
    lead_signal = existing or LeadSignal(
        signal_type=SignalType(signal["signal_type"]),
        state=signal["state"],
        normalized_business_name=signal["normalized_business_name"],
        business_name=signal["business_name"],
        signal_date=signal["signal_date"],
        title=signal["title"],
        grade=LeadSignalGrade(signal["grade"]),
        source_id=source.id,
        source_url=signal["source_url"],
    )
    lead_signal.county = signal.get("county")
    lead_signal.business_name = signal["business_name"]
    lead_signal.funder_name = signal.get("funder_name")
    lead_signal.summary = signal.get("summary")
    lead_signal.score = signal["score"]
    lead_signal.risk_score = signal["risk_score"]
    lead_signal.grade = LeadSignalGrade(signal["grade"])
    lead_signal.status = LeadSignalStatus(signal["status"])
    lead_signal.exclusion_reason = signal.get("exclusion_reason")
    lead_signal.compliance_flags = _string_list(signal.get("compliance_flags"))
    lead_signal.source_url = signal["source_url"]
    if payload.record_type == "case":
        lead_signal.case_id = source_entity_id
    elif payload.record_type == "ucc_filing":
        lead_signal.ucc_filing_id = source_entity_id
    session.add(lead_signal)
    session.flush()
    return created


def _upsert_case_document(session: Session, case: Case, payload: SignalPayload) -> None:
    text_content = payload.source_record.get("document_text")
    if not isinstance(text_content, str) or not text_content.strip():
        return

    title = str(payload.source_record.get("document_title") or "Initiating Document")
    document = session.scalar(
        select(CaseDocument).where(
            CaseDocument.case_id == case.id,
            CaseDocument.document_title == title,
        )
    )
    classification = classify_text(text_content)
    if document is None:
        document = CaseDocument(
            case_id=case.id,
            document_title=title,
            document_type="Complaint",
            source_url=payload.source_url,
        )
        session.add(document)
    document.filed_at = document_datetime_from_date(case.filing_date)
    document.storage_path = payload.raw_artifact_path
    document.text_content = text_content
    document.has_mca_keywords = bool(classification.keyword_hits)
    document.keyword_hits = list(classification.keyword_hits)


def _artifact_type_from_path(path: str) -> ArtifactType:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"html", "pdf", "csv", "json", "txt"}:
        return ArtifactType(suffix)
    return ArtifactType.MANUAL


def _sha256_file(path: str) -> str:
    from hashlib import sha256

    return sha256(Path(path).read_bytes()).hexdigest()


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, Iterable) and not isinstance(value, str):
        return [str(item) for item in value if str(item)]
    return []
