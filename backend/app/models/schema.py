from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    AccessMethod,
    ArtifactType,
    DeliveryMethod,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    SourceType,
    SuppressionType,
)


def _enum(enum_class: type, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda values: [item.value for item in values],
    )


IdColumn = UUID(as_uuid=True)
TextArray = ARRAY(Text)
JsonDict = dict[str, Any]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), nullable=False
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    access_method: Mapped[AccessMethod] = mapped_column(
        _enum(AccessMethod, "access_method"), nullable=False
    )
    terms_notes: Mapped[str | None] = mapped_column(Text)
    automation_allowed: Mapped[bool | None] = mapped_column(Boolean)
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ingestion_runs: Mapped[list[IngestionRun]] = relationship(back_populates="source")
    raw_artifacts: Mapped[list[RawArtifact]] = relationship(back_populates="source")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="ingestion_runs")
    raw_artifacts: Mapped[list[RawArtifact]] = relationship(back_populates="ingestion_run")


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_runs.id"), nullable=False
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        _enum(ArtifactType, "artifact_type"), nullable=False
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    artifact_metadata: Mapped[JsonDict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="raw_artifacts")
    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="raw_artifacts")


class Case(TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index(
            "uq_cases_state_court_name_case_number",
            "state",
            "court_name",
            "case_number",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    county: Mapped[str | None] = mapped_column(String(120))
    court_name: Mapped[str] = mapped_column(String(255), nullable=False)
    case_number: Mapped[str] = mapped_column(String(120), nullable=False)
    case_type: Mapped[str | None] = mapped_column(String(120))
    filing_date: Mapped[date | None] = mapped_column(Date)
    last_activity_date: Mapped[date | None] = mapped_column(Date)
    caption: Mapped[str | None] = mapped_column(Text)
    plaintiff_names: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    defendant_names: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    attorney_names: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_artifacts.id"))
    normalized_key: Mapped[str] = mapped_column(String(500), nullable=False)

    documents: Mapped[list[CaseDocument]] = relationship(back_populates="case")


class CaseDocument(Base):
    __tablename__ = "case_documents"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(120))
    document_title: Mapped[str | None] = mapped_column(Text)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text)
    text_content: Mapped[str | None] = mapped_column(Text)
    has_mca_keywords: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    keyword_hits: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    case: Mapped[Case] = relationship(back_populates="documents")


class UccFiling(TimestampMixin, Base):
    __tablename__ = "ucc_filings"
    __table_args__ = (
        Index("uq_ucc_filings_state_filing_number", "state", "filing_number", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    filing_number: Mapped[str] = mapped_column(String(120), nullable=False)
    filing_type: Mapped[str | None] = mapped_column(String(120))
    filing_date: Mapped[date | None] = mapped_column(Date)
    lapse_date: Mapped[date | None] = mapped_column(Date)
    debtor_name: Mapped[str | None] = mapped_column(Text)
    debtor_address: Mapped[str | None] = mapped_column(Text)
    secured_party_name: Mapped[str | None] = mapped_column(Text)
    secured_party_address: Mapped[str | None] = mapped_column(Text)
    collateral_text: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_artifacts.id"))
    normalized_key: Mapped[str] = mapped_column(String(500), nullable=False)


class BusinessEntity(Base):
    __tablename__ = "business_entities"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str | None] = mapped_column(String(120))
    principal_address: Mapped[str | None] = mapped_column(Text)
    mailing_address: Mapped[str | None] = mapped_column(Text)
    registered_agent_name: Mapped[str | None] = mapped_column(Text)
    registered_agent_address: Mapped[str | None] = mapped_column(Text)
    officers: Mapped[JsonDict] = mapped_column(JSONB, default=dict, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class McaFunder(Base):
    __tablename__ = "mca_funders"
    __table_args__ = (Index("uq_mca_funders_normalized_name", "normalized_name", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeadSignal(TimestampMixin, Base):
    __tablename__ = "lead_signals"
    __table_args__ = (
        Index(
            "uq_lead_signals_signal_type_state_business_date_funder",
            "signal_type",
            "state",
            "normalized_business_name",
            "signal_date",
            "funder_name",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    signal_type: Mapped[SignalType] = mapped_column(
        _enum(SignalType, "signal_type"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    county: Mapped[str | None] = mapped_column(String(120))
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_business_name: Mapped[str] = mapped_column(Text, nullable=False)
    funder_name: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"))
    ucc_filing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ucc_filings.id"))
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grade: Mapped[LeadSignalGrade] = mapped_column(
        _enum(LeadSignalGrade, "lead_signal_grade"), nullable=False
    )
    status: Mapped[LeadSignalStatus] = mapped_column(
        _enum(LeadSignalStatus, "lead_signal_status"),
        default=LeadSignalStatus.NEW,
        nullable=False,
    )
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    compliance_flags: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class BuyerAccount(Base):
    __tablename__ = "buyer_accounts"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    firm_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    states: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    counties: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    practice_tags: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rules: Mapped[list[BuyerRule]] = relationship(back_populates="buyer_account")


class BuyerRule(Base):
    __tablename__ = "buyer_rules"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    buyer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buyer_accounts.id"), nullable=False
    )
    state: Mapped[str | None] = mapped_column(String(2))
    counties: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    min_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_types: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    exclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    daily_limit: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    buyer_account: Mapped[BuyerAccount] = relationship(back_populates="rules")


class LeadDelivery(Base):
    __tablename__ = "lead_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    lead_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lead_signals.id"), nullable=False)
    buyer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("buyer_accounts.id"), nullable=False
    )
    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        _enum(DeliveryMethod, "delivery_method"), nullable=False
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    rejected_reason: Mapped[str | None] = mapped_column(Text)


class FormLead(Base):
    __tablename__ = "form_leads"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    preferred_contact_method: Mapped[str] = mapped_column(String(40), nullable=False)
    legal_issue_type: Mapped[str] = mapped_column(String(120), nullable=False)
    has_been_sued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    case_state: Mapped[str | None] = mapped_column(String(2))
    case_county: Mapped[str | None] = mapped_column(String(120))
    case_number: Mapped[str | None] = mapped_column(String(120))
    mca_funder_names: Mapped[list[str]] = mapped_column(TextArray, default=list, nullable=False)
    daily_weekly_payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_mca_balance_range: Mapped[str | None] = mapped_column(String(120))
    bank_account_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ucc_lien_issue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    court_deadline_date: Mapped[date | None] = mapped_column(Date)
    has_attorney: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    disclaimer_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    source_campaign: Mapped[str | None] = mapped_column(String(255))
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grade: Mapped[LeadSignalGrade] = mapped_column(
        _enum(LeadSignalGrade, "lead_signal_grade"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SuppressionListEntry(Base):
    __tablename__ = "suppression_list"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    suppression_type: Mapped[SuppressionType] = mapped_column(
        _enum(SuppressionType, "suppression_type"),
        nullable=False,
    )
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConsentEvent(Base):
    __tablename__ = "consent_events"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    lead_signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead_signals.id"))
    form_lead_id: Mapped[str | None] = mapped_column(String(120))
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buyer_disclosure: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(IdColumn, primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_metadata: Mapped[JsonDict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
