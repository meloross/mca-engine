from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enrichment.base import EnrichmentResult, LeadContactCandidate
from app.models import BusinessEntity, LeadSignal


class FloridaSunbizProvider:
    name = "florida_sunbiz"

    def __init__(self, session: Session) -> None:
        self.session = session

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        if lead_signal.state != "FL":
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)
        entity = self.session.scalar(
            select(BusinessEntity).where(
                BusinessEntity.state == "FL",
                BusinessEntity.normalized_name == lead_signal.normalized_business_name,
            )
        )
        if entity is None:
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)

        officer = _first_officer(entity.officers)
        contacts: list[LeadContactCandidate] = []
        if entity.registered_agent_name:
            contacts.append(
                LeadContactCandidate(
                    contact_type="registered_agent",
                    value=entity.registered_agent_name,
                    source_provider=self.name,
                    source_url=entity.source_url,
                    source_category="business_registry",
                    confidence=85,
                )
            )
        return EnrichmentResult(
            provider=self.name,
            status="partial" if officer is None else "success",
            owner_principal_name=officer[0] if officer else None,
            owner_principal_title=officer[1] if officer else None,
            registered_agent_name=entity.registered_agent_name,
            registered_agent_address=entity.registered_agent_address,
            business_address=entity.principal_address or entity.mailing_address,
            confidence=86 if officer else 76,
            source_url=entity.source_url,
            source_record_id=str(entity.id),
            raw_response={"entity_name": entity.entity_name, "status": entity.status},
            contacts=contacts,
        )


def _first_officer(officers: object) -> tuple[str, str | None] | None:
    if isinstance(officers, dict):
        raw_officers = officers.get("officers") or officers.get("managers") or []
        if isinstance(raw_officers, list) and raw_officers:
            first = raw_officers[0]
            if isinstance(first, dict):
                name = first.get("name")
                title = first.get("title")
                return (str(name), str(title) if title else None) if name else None
    return None
