from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.models import LeadSignal


@dataclass(frozen=True)
class LeadContactCandidate:
    contact_type: str
    value: str
    source_provider: str
    source_url: str | None = None
    source_category: str | None = None
    confidence: int = 0
    verification_status: str = "unverified"
    is_opt_in: bool = False
    contact_consent: bool = False
    contact_allowed: bool = False
    do_not_contact: bool = False


@dataclass(frozen=True)
class EnrichmentResult:
    provider: str
    status: str
    owner_principal_name: str | None = None
    owner_principal_title: str | None = None
    registered_agent_name: str | None = None
    registered_agent_address: str | None = None
    business_phone: str | None = None
    business_email: str | None = None
    business_website: str | None = None
    business_address: str | None = None
    google_place_id: str | None = None
    google_maps_url: str | None = None
    confidence: int = 0
    source_url: str | None = None
    source_record_id: str | None = None
    raw_response: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    contacts: list[LeadContactCandidate] = field(default_factory=list)


class EnrichmentProvider(Protocol):
    name: str

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        ...
