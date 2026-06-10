from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

HtmlFetcher = Callable[[str], str]


@dataclass(frozen=True)
class UccSearchRecord:
    state: str
    filing_number: str
    filing_type: str | None
    filing_date: date | None
    debtor_name: str | None
    debtor_address: str | None
    secured_party_name: str | None
    secured_party_address: str | None
    collateral_text: str | None
    source_url: str


@dataclass(frozen=True)
class UccLiveAdapterResult:
    source_code: str
    status: str
    records: tuple[UccSearchRecord, ...] = ()
    message: str = ""
    errors: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


class BaseUccLiveAdapter:
    source_code: str
    state: str
    base_url: str

    def __init__(self, html_fetcher: HtmlFetcher | None = None) -> None:
        self.html_fetcher = html_fetcher

    def run_for_secured_party(self, secured_party_name: str) -> UccLiveAdapterResult:
        if self.html_fetcher is None:
            return UccLiveAdapterResult(
                source_code=self.source_code,
                status="skipped",
                message=(
                    "No authorized live fetcher configured; use manual import "
                    "or enable a licensed path."
                ),
                metadata={"secured_party_name": secured_party_name},
            )
        html = self.html_fetcher(secured_party_name)
        return self.run_html(
            html,
            secured_party_name=secured_party_name,
            source_url=self.base_url,
        )

    def run_html(
        self,
        html: str,
        *,
        secured_party_name: str | None = None,
        source_url: str | None = None,
    ) -> UccLiveAdapterResult:
        from app.adapters.ucc.parser_utils import (
            contains_access_barrier,
            dedupe_ucc_records,
            parse_ucc_search_html,
        )

        if contains_access_barrier(html):
            return UccLiveAdapterResult(
                source_code=self.source_code,
                status="blocked",
                message="Access barrier detected; no CAPTCHA/login/payment bypass attempted.",
                metadata={"secured_party_name": secured_party_name},
            )
        records = dedupe_ucc_records(
            parse_ucc_search_html(
                html,
                state=self.state,
                secured_party_name=secured_party_name,
                source_url=source_url or self.base_url,
            )
        )
        return UccLiveAdapterResult(
            source_code=self.source_code,
            status="ok",
            records=tuple(records),
            message=f"Parsed {len(records)} UCC records.",
            metadata={"secured_party_name": secured_party_name},
        )
