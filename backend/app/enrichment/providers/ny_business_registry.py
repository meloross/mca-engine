from __future__ import annotations

from app.enrichment.base import EnrichmentResult
from app.models import LeadSignal


class NewYorkBusinessRegistryProvider:
    name = "ny_business_registry"

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        if lead_signal.state != "NY":
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)
        return EnrichmentResult(
            provider=self.name,
            status="partial",
            registered_agent_name=None,
            confidence=35,
            source_url="manual_import_required",
            raw_response={"note": "NY registry enrichment starts with manual imports only."},
        )
