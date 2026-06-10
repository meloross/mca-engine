from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.classifiers import classify_text
from app.compliance import normalize_business_name
from app.db import SessionLocal
from app.models import (
    AccessMethod,
    AuditLog,
    BuyerAccount,
    BuyerRule,
    Case,
    CaseDocument,
    FormLead,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    Source,
    SourceType,
    UccFiling,
)
from app.scoring import score_signal
from app.services.fl_importer import import_mock_fl_to_db
from app.services.form_leads import (
    DEFAULT_LEAD_FORM_DISCLAIMER,
    FORM_LEAD_SIGNAL_TYPE,
    create_form_lead,
)
from app.services.ny_importer import import_mock_ny_to_db

DEMO_AS_OF = date(2026, 6, 9)
TARGET_SIGNALS_PER_STATE = 25
TARGET_UCC_SIGNALS_PER_STATE = 10
TARGET_BUYERS = 5
TARGET_CONSENTED_FORM_LEADS = 10
TARGET_NO_CONSENT_FORM_LEADS = 5

DEMO_FUNDERS = (
    "Cloudfund",
    "Yellowstone Capital",
    "WCM Funding",
    "Capital Advance Services",
    "ABC Merchant Solutions",
    "Thryve Capital Funding",
    "Fundry",
    "Green Capital Funding",
)
DEMO_COUNTIES = {
    "NY": ("Kings", "New York", "Queens", "Nassau", "Suffolk", "Westchester"),
    "FL": ("Miami-Dade", "Broward", "Palm Beach", "Orange", "Hillsborough", "Duval"),
}


@dataclass(frozen=True)
class DemoBuyer:
    firm_name: str
    contact_name: str
    email: str
    phone: str
    states: list[str]
    counties: list[str]
    practice_tags: list[str]
    min_score: int
    state: str | None


async def seed_demo_data() -> dict[str, int]:
    with SessionLocal() as session:
        await import_mock_ny_to_db(session)
        await import_mock_fl_to_db(session)

        _ensure_demo_signals(session, state="NY", target=TARGET_SIGNALS_PER_STATE)
        _ensure_demo_signals(session, state="FL", target=TARGET_SIGNALS_PER_STATE)
        _ensure_demo_ucc_signals(session, state="NY", target=TARGET_UCC_SIGNALS_PER_STATE)
        _ensure_demo_ucc_signals(session, state="FL", target=TARGET_UCC_SIGNALS_PER_STATE)
        _ensure_demo_suppressed_excluded_signals(session, target=5)
        _ensure_demo_buyers_and_rules(session)
        _ensure_demo_form_leads(
            session,
            consented_target=TARGET_CONSENTED_FORM_LEADS,
            no_consent_target=TARGET_NO_CONSENT_FORM_LEADS,
        )

        summary = _summary(session)
        session.add(
            AuditLog(
                actor="system",
                action="seed_demo_data",
                entity_type="demo",
                entity_id="local",
                event_metadata=summary,
            )
        )
        session.commit()
        return summary


def main() -> None:
    summary = asyncio.run(seed_demo_data())
    print(json.dumps(summary, indent=2, sort_keys=True))


def _ensure_demo_signals(session: Session, *, state: str, target: int) -> None:
    current = _state_signal_count(session, state)
    if current >= target:
        return

    source = _get_or_create_source(
        session,
        name=f"{state} Demo Seed Cases",
        state=state,
        source_type=SourceType.COURT_NEW_CASES,
        base_url=f"https://demo.local/{state.lower()}/cases",
    )
    session.flush()

    for sequence in range(current + 1, target + 1):
        county = DEMO_COUNTIES[state][sequence % len(DEMO_COUNTIES[state])]
        funder = DEMO_FUNDERS[sequence % len(DEMO_FUNDERS)]
        business = f"Demo {state} Merchant {sequence:02d} LLC"
        filing_date = DEMO_AS_OF - timedelta(days=sequence % 7)
        court_name = f"Demo {county} Commercial Court"
        case_number = f"DEMO-{state}-2026-{sequence:04d}"
        caption = f"{funder} LLC v. {business}"
        source_url = f"https://demo.local/{state.lower()}/cases/{case_number}"
        document_text = (
            "Merchant cash advance complaint alleging revenue purchase agreement default, "
            "daily ACH debit, purchased amount, bank restraint, UCC lien, and confession "
            "of judgment exposure."
        )

        case = _get_or_create_case(
            session,
            state=state,
            county=county,
            court_name=court_name,
            case_number=case_number,
            caption=caption,
            filing_date=filing_date,
            funder=funder,
            business=business,
            source=source,
            source_url=source_url,
        )
        _ensure_case_document(session, case=case, source_url=source_url, text=document_text)

        record = {
            "signal_type": SignalType.LITIGATION_NEW_CASE.value,
            "state": state,
            "county": county,
            "business_name": business,
            "funder_name": funder,
            "case_caption": caption,
            "filing_date": filing_date,
            "document_text": document_text,
            "plaintiff_names": [funder],
            "defendant_names": [business],
            "has_defense_attorney": False,
            "source_automation_allowed": True,
        }
        score = score_signal(record, as_of=DEMO_AS_OF)
        _upsert_demo_signal(
            session,
            source=source,
            case_id=case.id,
            ucc_filing_id=None,
            signal_type=SignalType.LITIGATION_NEW_CASE,
            state=state,
            county=county,
            business=business,
            funder=score.funder_match.matched_funder or funder,
            signal_date=filing_date,
            title=f"Demo {state} MCA litigation signal: {business}",
            summary="Synthetic demo litigation lead generated from mock public-record data.",
            score=score.score,
            risk_score=score.risk_score,
            grade=score.grade,
            status="new",
            compliance_flags=["mock", "demo_seed", "attorney_intelligence_only"],
            source_url=source_url,
        )


def _ensure_demo_ucc_signals(session: Session, *, state: str, target: int) -> None:
    current = _state_ucc_signal_count(session, state)
    if current >= target:
        return

    for sequence in range(current + 1, target + 1):
        source = _get_or_create_source(
            session,
            name="Demo Seed UCC Registry",
            state=state,
            source_type=SourceType.UCC_REGISTRY,
            base_url=f"https://demo.local/{state.lower()}/ucc",
        )
        session.flush()
        funder = DEMO_FUNDERS[sequence % len(DEMO_FUNDERS)]
        business = f"Demo {state} UCC Merchant {sequence:02d} LLC"
        county = DEMO_COUNTIES[state][sequence % len(DEMO_COUNTIES[state])]
        filing_number = f"DEMO-{state}-UCC-2026-{sequence:04d}"
        filing_date = DEMO_AS_OF - timedelta(days=sequence % 8)
        ucc = session.scalar(
            select(UccFiling).where(
                UccFiling.state == state,
                UccFiling.filing_number == filing_number,
            )
        )
        if ucc is None:
            ucc = UccFiling(
                state=state,
                filing_number=filing_number,
                filing_type="UCC-1",
                filing_date=filing_date,
                lapse_date=date(2031, 6, 1),
                debtor_name=business,
                debtor_address=f"{100 + sequence} Demo Ave, {state}",
                secured_party_name=funder,
                secured_party_address="Demo secured party address",
                collateral_text=(
                    "All future receivables, payment processor proceeds, lockbox rights, "
                    "and merchant cash advance remittances."
                ),
                source_id=source.id,
                source_url=f"https://demo.local/ucc/{filing_number}",
                normalized_key=f"{state}:UCC:{filing_number}",
            )
            session.add(ucc)
            session.flush()

        record = {
            "signal_type": SignalType.UCC_INITIAL.value,
            "state": state,
            "county": county,
            "business_name": business,
            "funder_name": funder,
            "secured_party_name": funder,
            "debtor_name": business,
            "defendant_names": [business],
            "ucc_collateral_text": ucc.collateral_text,
            "filing_date": filing_date,
            "source_automation_allowed": True,
            "multiple_ucc_filings_count": 2 if sequence % 3 == 0 else 1,
        }
        score = score_signal(record, as_of=DEMO_AS_OF)
        _upsert_demo_signal(
            session,
            source=source,
            ucc_filing_id=ucc.id,
            signal_type=SignalType.UCC_INITIAL,
            state=state,
            county=county,
            business=business,
            funder=score.funder_match.matched_funder or funder,
            signal_date=filing_date,
            title=f"Demo {state} MCA UCC signal: {business}",
            summary="Synthetic demo UCC lead generated from mock UCC data.",
            score=score.score,
            risk_score=score.risk_score,
            grade=score.grade,
            status="new",
            compliance_flags=["mock", "demo_seed", "ucc_signal"],
            source_url=f"https://demo.local/ucc/{filing_number}",
        )


def _ensure_demo_suppressed_excluded_signals(session: Session, *, target: int) -> None:
    current = sum(
        "export_filter_demo" in signal.compliance_flags
        for signal in session.scalars(select(LeadSignal)).all()
    )
    if current >= target:
        return

    for sequence in range(current + 1, target + 1):
        state = "NY" if sequence % 2 else "FL"
        source = _get_or_create_source(
            session,
            name="Demo Seed Export Filter Cases",
            state=state,
            source_type=SourceType.COURT_NEW_CASES,
            base_url=f"https://demo.local/{state.lower()}/export-filter-cases",
        )
        session.flush()
        county = DEMO_COUNTIES[state][sequence % len(DEMO_COUNTIES[state])]
        funder = DEMO_FUNDERS[sequence % len(DEMO_FUNDERS)]
        business = f"Demo Filtered Merchant {sequence:02d} LLC"
        status = "suppressed" if sequence <= 3 else "excluded"
        grade = "B" if status == "suppressed" else "EXCLUDE"
        score = 62 if status == "suppressed" else 0
        case_number = f"DEMO-FILTER-{state}-{sequence:04d}"
        source_url = f"https://demo.local/export-filter-cases/{case_number}"
        case = _get_or_create_case(
            session,
            state=state,
            county=county,
            court_name=f"Demo {county} Commercial Court",
            case_number=case_number,
            caption=f"{funder} LLC v. {business}",
            filing_date=DEMO_AS_OF,
            funder=funder,
            business=business,
            source=source,
            source_url=source_url,
        )
        _ensure_case_document(
            session,
            case=case,
            source_url=source_url,
            text="Merchant cash advance complaint with export filter demo status.",
        )
        _upsert_demo_signal(
            session,
            source=source,
            case_id=case.id,
            signal_type=SignalType.LITIGATION_NEW_CASE,
            state=state,
            county=county,
            business=business,
            funder=funder,
            signal_date=DEMO_AS_OF,
            title=f"Demo {status} MCA signal: {business}",
            summary="Synthetic demo row used to validate export omission filters.",
            score=score,
            risk_score=25 if status == "suppressed" else 100,
            grade=grade,
            status=status,
            compliance_flags=["mock", "demo_seed", "export_filter_demo"],
            source_url=source_url,
            exclusion_reason="demo export filter exclusion" if status == "excluded" else None,
        )


def _ensure_demo_buyers_and_rules(session: Session) -> None:
    buyers = (
        DemoBuyer(
            firm_name="Empire MCA Defense LLP",
            contact_name="Jordan Lee",
            email="intake-ny@example.com",
            phone="555-0101",
            states=["NY"],
            counties=["Kings", "New York", "Queens"],
            practice_tags=["mca_defense", "commercial_litigation"],
            min_score=75,
            state="NY",
        ),
        DemoBuyer(
            firm_name="Florida Merchant Defense Group",
            contact_name="Casey Morgan",
            email="intake-fl@example.com",
            phone="555-0102",
            states=["FL"],
            counties=["Miami-Dade", "Broward", "Palm Beach"],
            practice_tags=["mca_defense", "ucc_lien"],
            min_score=70,
            state="FL",
        ),
        DemoBuyer(
            firm_name="Southeast Receivables Counsel",
            contact_name="Riley Patel",
            email="routing-se@example.com",
            phone="555-0103",
            states=["FL"],
            counties=["Orange", "Hillsborough", "Duval"],
            practice_tags=["mca_defense", "bank_restraint"],
            min_score=55,
            state="FL",
        ),
        DemoBuyer(
            firm_name="Northeast Commercial Defense",
            contact_name="Taylor Kim",
            email="routing-ne@example.com",
            phone="555-0104",
            states=["NY"],
            counties=["Nassau", "Suffolk", "Westchester"],
            practice_tags=["mca_defense", "coj"],
            min_score=55,
            state="NY",
        ),
        DemoBuyer(
            firm_name="National MCA Intake Network",
            contact_name="Morgan Avery",
            email="routing-national@example.com",
            phone="555-0105",
            states=["NY", "FL"],
            counties=[],
            practice_tags=["mca_defense", "opt_in"],
            min_score=80,
            state=None,
        ),
    )

    for buyer_data in buyers:
        buyer = session.scalar(select(BuyerAccount).where(BuyerAccount.email == buyer_data.email))
        if buyer is None:
            buyer = BuyerAccount(
                firm_name=buyer_data.firm_name,
                contact_name=buyer_data.contact_name,
                email=buyer_data.email,
                phone=buyer_data.phone,
                states=buyer_data.states,
                counties=buyer_data.counties,
                practice_tags=buyer_data.practice_tags,
                active=True,
            )
            session.add(buyer)
            session.flush()

        existing_rule = session.scalar(
            select(BuyerRule).where(
                BuyerRule.buyer_account_id == buyer.id,
                BuyerRule.state == buyer_data.state,
            )
        )
        if existing_rule is None:
            session.add(
                BuyerRule(
                    buyer_account_id=buyer.id,
                    state=buyer_data.state,
                    counties=buyer_data.counties,
                    min_score=buyer_data.min_score,
                    signal_types=[
                        SignalType.LITIGATION_NEW_CASE.value,
                        SignalType.UCC_INITIAL.value,
                        FORM_LEAD_SIGNAL_TYPE,
                    ],
                    exclusive=False,
                    daily_limit=25,
                    active=True,
                )
            )
    session.commit()


def _ensure_demo_form_leads(
    session: Session,
    *,
    consented_target: int,
    no_consent_target: int,
) -> None:
    consented_current = (
        session.scalar(
            select(func.count())
            .select_from(FormLead)
            .where(FormLead.source_campaign == "investor-demo-consented")
        )
        or 0
    )
    no_consent_current = (
        session.scalar(
            select(func.count())
            .select_from(FormLead)
            .where(FormLead.source_campaign == "investor-demo-no-consent")
        )
        or 0
    )
    _create_demo_form_leads(
        session,
        start=consented_current + 1,
        stop=consented_target,
        consent_to_contact=True,
        source_campaign="investor-demo-consented",
    )
    _create_demo_form_leads(
        session,
        start=no_consent_current + 1,
        stop=no_consent_target,
        consent_to_contact=False,
        source_campaign="investor-demo-no-consent",
    )


def _create_demo_form_leads(
    session: Session,
    *,
    start: int,
    stop: int,
    consent_to_contact: bool,
    source_campaign: str,
) -> None:
    if start > stop:
        return

    label = "consented" if consent_to_contact else "no-consent"
    for sequence in range(start, stop + 1):
        email = f"demo-{label}-form-lead-{sequence:02d}@example.com"
        if session.scalar(select(FormLead).where(FormLead.email == email)) is not None:
            continue
        state = "NY" if sequence % 2 else "FL"
        county = DEMO_COUNTIES[state][sequence % len(DEMO_COUNTIES[state])]
        funder = DEMO_FUNDERS[sequence % len(DEMO_FUNDERS)]
        payload = SimpleNamespace(
            business_name=f"Opt In Demo {label.title()} Merchant {sequence:02d} LLC",
            state=state,
            has_been_sued=True,
            bank_account_frozen=sequence % 3 != 0,
            ucc_lien_issue=True,
            mca_funder_names=[funder],
            daily_weekly_payment_amount=Decimal("1850.00") + Decimal(sequence * 100),
            total_mca_balance_range="over $50k",
            court_deadline_date=date.today() + timedelta(days=sequence % 10),
            has_attorney=sequence % 5 == 0,
            contact_name=f"Demo Contact {sequence:02d}",
            email=email,
            phone=f"555-02{sequence:02d}",
            preferred_contact_method="email",
            legal_issue_type="mca_defense",
            case_state=state,
            case_county=county,
            case_number=f"DEMO-FORM-{state}-{sequence:04d}",
            consent_to_contact=consent_to_contact,
            consent_text=(
                "I agree that an attorney or legal service provider may contact me about "
                "my MCA defense request."
            ),
            page_url="https://demo.local/lead-form/mca-defense",
            source_campaign=source_campaign,
            disclaimer_text=DEFAULT_LEAD_FORM_DISCLAIMER,
        )
        create_form_lead(
            session,
            payload=payload,
            ip_address=f"192.0.2.{sequence}",
            user_agent="demo-seed/1.0",
        )


def _get_or_create_source(
    session: Session,
    *,
    name: str,
    state: str,
    source_type: SourceType,
    base_url: str,
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
        terms_notes="Synthetic demo/mock source. No live automation or real credentials used.",
        automation_allowed=True,
        requires_login=False,
        requires_payment=False,
    )
    session.add(source)
    return source


def _get_or_create_case(
    session: Session,
    *,
    state: str,
    county: str,
    court_name: str,
    case_number: str,
    caption: str,
    filing_date: date,
    funder: str,
    business: str,
    source: Source,
    source_url: str,
) -> Case:
    case = session.scalar(
        select(Case).where(
            Case.state == state,
            Case.court_name == court_name,
            Case.case_number == case_number,
        )
    )
    if case is not None:
        return case
    case = Case(
        state=state,
        county=county,
        court_name=court_name,
        case_number=case_number,
        case_type="Commercial",
        filing_date=filing_date,
        last_activity_date=filing_date,
        caption=caption,
        plaintiff_names=[funder],
        defendant_names=[business],
        attorney_names=[],
        source_id=source.id,
        source_url=source_url,
        normalized_key=f"{state}:CASE:{court_name.upper()}:{case_number}",
    )
    session.add(case)
    session.flush()
    return case


def _ensure_case_document(session: Session, *, case: Case, source_url: str, text: str) -> None:
    existing = session.scalar(
        select(CaseDocument).where(
            CaseDocument.case_id == case.id,
            CaseDocument.document_title == "Demo Complaint",
        )
    )
    if existing is not None:
        return
    classification = classify_text(text)
    session.add(
        CaseDocument(
            case_id=case.id,
            document_type="Complaint",
            document_title="Demo Complaint",
            filed_at=datetime.combine(case.filing_date or DEMO_AS_OF, datetime.min.time(), UTC),
            source_url=source_url,
            storage_path="data/artifacts/demo/demo-complaint.txt",
            text_content=text,
            has_mca_keywords=bool(classification.keyword_hits),
            keyword_hits=list(classification.keyword_hits),
        )
    )


def _upsert_demo_signal(
    session: Session,
    *,
    source: Source,
    case_id: UUID | None = None,
    ucc_filing_id: UUID | None = None,
    signal_type: SignalType = SignalType.LITIGATION_NEW_CASE,
    state: str,
    county: str,
    business: str,
    funder: str,
    signal_date: date,
    title: str,
    summary: str,
    score: int,
    risk_score: int,
    grade: str,
    status: str,
    compliance_flags: list[str],
    source_url: str,
    exclusion_reason: str | None = None,
) -> None:
    normalized_business = normalize_business_name(business)
    existing = session.scalar(
        select(LeadSignal).where(
            LeadSignal.signal_type == signal_type,
            LeadSignal.state == state,
            LeadSignal.normalized_business_name == normalized_business,
            LeadSignal.signal_date == signal_date,
            LeadSignal.funder_name == funder,
        )
    )
    signal = existing or LeadSignal(
        signal_type=signal_type,
        state=state,
        normalized_business_name=normalized_business,
        business_name=business,
        signal_date=signal_date,
        grade=LeadSignalGrade(grade),
        status=LeadSignalStatus(status),
        source_id=source.id,
        source_url=source_url,
        title=title,
    )
    signal.county = county
    signal.funder_name = funder
    signal.case_id = case_id
    signal.ucc_filing_id = ucc_filing_id
    signal.title = title
    signal.summary = summary
    signal.score = score
    signal.risk_score = risk_score
    signal.grade = LeadSignalGrade(grade)
    signal.status = LeadSignalStatus(status)
    signal.exclusion_reason = exclusion_reason
    signal.compliance_flags = compliance_flags
    signal.source_id = source.id
    signal.source_url = source_url
    session.add(signal)
    session.commit()


def _state_signal_count(session: Session, state: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(LeadSignal).where(LeadSignal.state == state)
        )
        or 0
    )


def _state_ucc_signal_count(session: Session, state: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(LeadSignal)
            .where(
                LeadSignal.state == state,
                LeadSignal.signal_type == SignalType.UCC_INITIAL,
            )
        )
        or 0
    )


def _summary(session: Session) -> dict[str, int]:
    return {
        "ny_signals": _state_signal_count(session, "NY"),
        "fl_signals": _state_signal_count(session, "FL"),
        "ny_ucc_signals": _state_ucc_signal_count(session, "NY"),
        "fl_ucc_signals": _state_ucc_signal_count(session, "FL"),
        "ucc_filings": session.scalar(select(func.count()).select_from(UccFiling)) or 0,
        "buyer_accounts": session.scalar(select(func.count()).select_from(BuyerAccount)) or 0,
        "buyer_rules": session.scalar(select(func.count()).select_from(BuyerRule)) or 0,
        "form_leads": session.scalar(select(func.count()).select_from(FormLead)) or 0,
        "consented_form_leads": session.scalar(
            select(func.count()).select_from(FormLead).where(FormLead.consent_to_contact.is_(True))
        )
        or 0,
        "no_consent_form_leads": session.scalar(
            select(func.count()).select_from(FormLead).where(FormLead.consent_to_contact.is_(False))
        )
        or 0,
    }


if __name__ == "__main__":
    main()
