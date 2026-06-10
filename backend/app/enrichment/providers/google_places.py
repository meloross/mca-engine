from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import httpx

from app.config import settings
from app.enrichment.base import EnrichmentResult, LeadContactCandidate
from app.enrichment.confidence import name_match_confidence
from app.models import LeadSignal

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,nationalPhoneNumber,internationalPhoneNumber,"
    "websiteUri,googleMapsUri,businessStatus"
)


class GooglePlacesProvider:
    name = "google_places"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._last_request_at = 0.0

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        if not settings.google_places_enabled:
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)
        if not settings.google_places_api_key:
            return EnrichmentResult(
                provider=self.name,
                status="failed",
                confidence=0,
                error="GOOGLE_PLACES_API_KEY is not configured.",
            )

        try:
            search = await self._post_json(
                TEXT_SEARCH_URL,
                {"textQuery": self._query(lead_signal), "pageSize": 3},
                "places.id,places.displayName,places.formattedAddress",
            )
            places = search.get("places", [])
            if not isinstance(places, list) or not places:
                return EnrichmentResult(provider=self.name, status="skipped", confidence=0)
            candidate = self._best_candidate(lead_signal, places)
            if candidate is None:
                return EnrichmentResult(provider=self.name, status="skipped", confidence=0)

            place_id = str(candidate["id"])
            details = await self._get_json(
                DETAILS_URL.format(place_id=place_id),
                DETAILS_FIELD_MASK,
            )
            display_name = _display_name(details) or _display_name(candidate) or ""
            confidence = name_match_confidence(
                lead_signal.business_name,
                display_name,
            )
            if confidence < settings.google_places_min_confidence:
                return EnrichmentResult(
                    provider=self.name,
                    status="skipped",
                    confidence=confidence,
                    error="Weak Google Places match rejected.",
                )
            contacts = self._contacts(details, confidence)
            return EnrichmentResult(
                provider=self.name,
                status="success",
                business_phone=_phone(details),
                business_website=_string(details.get("websiteUri")),
                business_address=_string(details.get("formattedAddress")),
                google_place_id=place_id,
                google_maps_url=_string(details.get("googleMapsUri")),
                confidence=confidence,
                source_url=_string(details.get("googleMapsUri")),
                source_record_id=place_id,
                raw_response=_safe_response(details),
                contacts=contacts,
            )
        except httpx.HTTPError as exc:
            return EnrichmentResult(
                provider=self.name,
                status="failed",
                confidence=0,
                error=str(exc),
            )

    async def _post_json(
        self,
        url: str,
        payload: dict[str, object],
        field_mask: str,
    ) -> dict[str, Any]:
        await self._rate_limit()
        async with self._client_context() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._headers(field_mask),
                timeout=settings.website_crawler_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return cast("dict[str, Any]", payload) if isinstance(payload, dict) else {}

    async def _get_json(self, url: str, field_mask: str) -> dict[str, Any]:
        await self._rate_limit()
        async with self._client_context() as client:
            response = await client.get(
                url,
                headers=self._headers(field_mask),
                timeout=settings.website_crawler_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return cast("dict[str, Any]", payload) if isinstance(payload, dict) else {}

    async def _rate_limit(self) -> None:
        minimum_gap = 60 / max(settings.google_places_max_requests_per_minute, 1)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < minimum_gap:
            await asyncio.sleep(minimum_gap - elapsed)
        self._last_request_at = time.monotonic()

    @asynccontextmanager
    async def _client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient() as client:
            yield client

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_places_api_key or "",
            "X-Goog-FieldMask": field_mask,
        }

    def _query(self, lead_signal: LeadSignal) -> str:
        parts = [lead_signal.business_name, lead_signal.county or "", lead_signal.state]
        return " ".join(part for part in parts if part)

    def _best_candidate(
        self,
        lead_signal: LeadSignal,
        places: list[object],
    ) -> dict[str, object] | None:
        best: tuple[int, dict[str, object]] | None = None
        for place in places:
            if not isinstance(place, dict) or "id" not in place:
                continue
            confidence = name_match_confidence(
                lead_signal.business_name,
                _display_name(place) or "",
            )
            if best is None or confidence > best[0]:
                best = (confidence, place)
        if best is None or best[0] < settings.google_places_min_confidence:
            return None
        return best[1]

    def _contacts(
        self,
        details: dict[str, object],
        confidence: int,
    ) -> list[LeadContactCandidate]:
        contacts: list[LeadContactCandidate] = []
        phone = _phone(details)
        website = _string(details.get("websiteUri"))
        source_url = _string(details.get("googleMapsUri"))
        if phone:
            contacts.append(
                LeadContactCandidate(
                    contact_type="business_phone",
                    value=phone,
                    source_provider=self.name,
                    source_url=source_url,
                    source_category="google_places",
                    confidence=confidence,
                )
            )
        if website:
            contacts.append(
                LeadContactCandidate(
                    contact_type="website",
                    value=website,
                    source_provider=self.name,
                    source_url=source_url,
                    source_category="google_places",
                    confidence=confidence,
                )
            )
        return contacts


def _display_name(value: dict[str, object]) -> str | None:
    display_name = value.get("displayName")
    if isinstance(display_name, dict):
        text = display_name.get("text")
        return str(text) if text else None
    return str(display_name) if display_name else None


def _phone(value: dict[str, object]) -> str | None:
    return _string(value.get("nationalPhoneNumber") or value.get("internationalPhoneNumber"))


def _string(value: object) -> str | None:
    return str(value) if value else None


def _safe_response(value: dict[str, object]) -> dict[str, object]:
    return {key: item for key, item in value.items() if key != "apiKey"}
