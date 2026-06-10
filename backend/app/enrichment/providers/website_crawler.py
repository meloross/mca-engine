from __future__ import annotations

import re
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings
from app.enrichment.base import EnrichmentResult, LeadContactCandidate
from app.enrichment.matching import domain_from_url, normalize_us_phone
from app.models import LeadSignal

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
LINK_PATTERN = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
IGNORED_EMAIL_PREFIXES = ("example@", "test@", "noreply@", "no-reply@", "donotreply@")


class WebsiteCrawlerProvider:
    name = "website_crawler"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def enrich(self, lead_signal: LeadSignal) -> EnrichmentResult:
        if not settings.website_crawler_enabled:
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)
        if not lead_signal.business_website:
            return EnrichmentResult(provider=self.name, status="skipped", confidence=0)

        base_url = lead_signal.business_website
        domain = domain_from_url(base_url)
        visited: set[str] = set()
        queue: deque[str] = deque([base_url])
        emails: dict[str, str] = {}
        phones: dict[str, str] = {}

        async with self._client_context() as client:
            while queue and len(visited) < settings.website_crawler_max_pages:
                url = queue.popleft()
                if url in visited or domain_from_url(url) != domain:
                    continue
                visited.add(url)
                try:
                    response = await client.get(
                        url,
                        timeout=settings.website_crawler_timeout_seconds,
                    )
                    if response.status_code >= 400:
                        continue
                except httpx.HTTPError:
                    continue
                html = response.text
                for email in _extract_emails(html):
                    emails.setdefault(email, url)
                for phone in _extract_phones(html):
                    phones.setdefault(phone, url)
                for link in _candidate_links(url, html, domain):
                    is_under_page_limit = (
                        len(visited) + len(queue) < settings.website_crawler_max_pages
                    )
                    if link not in visited and is_under_page_limit:
                        queue.append(link)

        contacts: list[LeadContactCandidate] = []
        for email, source_url in emails.items():
            contacts.append(
                LeadContactCandidate(
                    contact_type="business_email",
                    value=email,
                    source_provider=self.name,
                    source_url=source_url,
                    source_category="website",
                    confidence=_email_confidence(email, domain),
                )
            )
        for phone, source_url in phones.items():
            contacts.append(
                LeadContactCandidate(
                    contact_type="business_phone",
                    value=phone,
                    source_provider=self.name,
                    source_url=source_url,
                    source_category="website",
                    confidence=75,
                )
            )
        return EnrichmentResult(
            provider=self.name,
            status="partial" if contacts else "skipped",
            business_email=next(iter(emails), None),
            business_phone=next(iter(phones), None),
            confidence=75 if contacts else 0,
            source_url=base_url,
            raw_response={
                "visited_pages": list(visited),
                "emails": list(emails),
                "phones": list(phones),
            },
            contacts=contacts,
        )

    @asynccontextmanager
    async def _client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient(follow_redirects=True) as client:
            yield client


def _extract_emails(html: str) -> list[str]:
    found = []
    for email in EMAIL_PATTERN.findall(html):
        lowered = email.lower()
        if lowered.startswith(IGNORED_EMAIL_PREFIXES):
            continue
        found.append(lowered)
    return list(dict.fromkeys(found))


def _extract_phones(html: str) -> list[str]:
    phones: list[str] = []
    for match in PHONE_PATTERN.findall(html):
        normalized = normalize_us_phone(match)
        if normalized:
            phones.append(normalized)
    return list(dict.fromkeys(phones))


def _candidate_links(current_url: str, html: str, domain: str) -> list[str]:
    candidates: list[str] = []
    interesting = ("contact", "about", "legal", "locations")
    for raw_link in LINK_PATTERN.findall(html):
        absolute = urljoin(current_url, raw_link)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if domain_from_url(absolute) != domain:
            continue
        path = parsed.path.lower()
        if any(token in path for token in interesting):
            candidates.append(absolute.split("#", 1)[0])
    return list(dict.fromkeys(candidates))


def _email_confidence(email: str, domain: str) -> int:
    return 78 if email.split("@", 1)[-1].removeprefix("www.") == domain else 58
