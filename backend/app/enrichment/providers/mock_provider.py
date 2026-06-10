from __future__ import annotations

import hashlib

from app.enrichment.base import EnrichmentResult, LeadContactCandidate
from app.models import LeadSignal


class MockEnrichmentProvider:
    name = "mock_enrichment"

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        digest = hashlib.sha256(lead_signal.lead_reference_id.encode()).hexdigest()
        suffix = int(digest[:4], 16) % 9000 + 1000
        website_slug = lead_signal.normalized_business_name.lower().replace(" ", "-")
        website = f"https://{website_slug}.example.com"
        email = f"intake-{suffix}@example.com"
        phone = f"555-01{suffix % 100:02d}"
        owner_name = f"Demo Principal {suffix % 97:02d}"
        contacts = [
            LeadContactCandidate(
                contact_type="business_phone",
                value=phone,
                source_provider=self.name,
                source_url=website,
                source_category="mock",
                confidence=82,
            ),
            LeadContactCandidate(
                contact_type="business_email",
                value=email,
                source_provider=self.name,
                source_url=website,
                source_category="mock",
                confidence=78,
            ),
            LeadContactCandidate(
                contact_type="website",
                value=website,
                source_provider=self.name,
                source_url=website,
                source_category="mock",
                confidence=85,
            ),
            LeadContactCandidate(
                contact_type="owner_principal",
                value=owner_name,
                source_provider=self.name,
                source_category="mock",
                confidence=72,
            ),
        ]
        return EnrichmentResult(
            provider=self.name,
            status="success",
            owner_principal_name=owner_name,
            owner_principal_title="Principal",
            registered_agent_name=f"Demo Registered Agent {suffix % 53:02d}",
            registered_agent_address=f"{suffix} Demo Agent Ave",
            business_phone=phone,
            business_email=email,
            business_website=website,
            business_address=f"{suffix} Demo Business Rd",
            confidence=82,
            source_url=website,
            source_record_id=lead_signal.lead_reference_id,
            raw_response={"provider": self.name, "demo": True},
            contacts=contacts,
        )
