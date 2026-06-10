from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.form_leads import DEFAULT_LEAD_FORM_DISCLAIMER


class SignalReviewRequest(BaseModel):
    status: Literal["reviewed", "suppressed", "excluded"]
    notes: str | None = None
    exclusion_reason: str | None = None


class SignalDeliveryRequest(BaseModel):
    buyer_account_id: UUID
    delivery_method: Literal["dashboard", "email", "webhook", "csv"]


class BuyerCreateRequest(BaseModel):
    firm_name: str = Field(min_length=1)
    contact_name: str | None = None
    email: str
    phone: str | None = None
    states: list[str] = Field(default_factory=list)
    counties: list[str] = Field(default_factory=list)
    practice_tags: list[str] = Field(default_factory=list)
    active: bool = True


class BuyerRuleCreateRequest(BaseModel):
    buyer_account_id: UUID
    state: str | None = Field(default=None, min_length=2, max_length=2)
    counties: list[str] = Field(default_factory=list)
    min_score: int = Field(default=0, ge=0)
    signal_types: list[str] = Field(default_factory=list)
    exclusive: bool = False
    daily_limit: int | None = Field(default=None, ge=1)
    active: bool = True


class McaDefenseLeadFormRequest(BaseModel):
    business_name: str = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    has_been_sued: bool
    bank_account_frozen: bool = False
    ucc_lien_issue: bool = False
    mca_funder_names: list[str] = Field(default_factory=list)
    daily_weekly_payment_amount: Decimal | None = Field(default=None, ge=0)
    total_mca_balance_range: str | None = None
    court_deadline_date: date | None = None
    has_attorney: bool = False
    contact_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone: str | None = None
    preferred_contact_method: Literal["email", "phone", "text"] = "email"
    legal_issue_type: str = "mca_defense"
    case_state: str | None = Field(default=None, min_length=2, max_length=2)
    case_county: str | None = None
    case_number: str | None = None
    consent_to_contact: bool
    consent_text: str = Field(min_length=1)
    page_url: str = Field(min_length=1)
    source_campaign: str | None = None
    disclaimer_text: str = DEFAULT_LEAD_FORM_DISCLAIMER
