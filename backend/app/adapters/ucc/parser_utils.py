from __future__ import annotations

from datetime import date
from html.parser import HTMLParser
from typing import Any

from app.adapters.parsing import parse_html_rows
from app.adapters.ucc.base_ucc_live import UccSearchRecord

ACCESS_BARRIER_TERMS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "access denied",
    "sign in",
    "login required",
    "create account",
    "payment required",
    "blocked",
)

HEADER_ALIASES = {
    "filing number": "filing_number",
    "filing #": "filing_number",
    "file number": "filing_number",
    "filing type": "filing_type",
    "type": "filing_type",
    "filing date": "filing_date",
    "file date": "filing_date",
    "date": "filing_date",
    "debtor": "debtor_name",
    "debtor name": "debtor_name",
    "debtor address": "debtor_address",
    "secured party": "secured_party_name",
    "secured party name": "secured_party_name",
    "secured party address": "secured_party_address",
    "collateral": "collateral_text",
    "collateral text": "collateral_text",
    "source": "source_url",
    "source url": "source_url",
}


def contains_access_barrier(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ACCESS_BARRIER_TERMS)


def parse_ucc_search_html(
    html: str,
    *,
    state: str,
    secured_party_name: str | None = None,
    source_url: str,
) -> list[UccSearchRecord]:
    if contains_access_barrier(html):
        return []

    data_rows = parse_html_rows(html, record_name="ucc")
    if data_rows:
        return [
            _row_to_record(
                row,
                state=state,
                secured_party_name=secured_party_name,
                source_url=source_url,
            )
            for row in data_rows
            if row.get("filing_number")
        ]

    table_rows = _parse_plain_table_rows(html)
    if not table_rows:
        return []

    headers = [_normalize_header(cell) for cell in table_rows[0]]
    records: list[UccSearchRecord] = []
    for cells in table_rows[1:]:
        row = {
            header: cells[index].strip()
            for index, header in enumerate(headers)
            if header and index < len(cells) and cells[index].strip()
        }
        if row.get("filing_number"):
            records.append(
                _row_to_record(
                    row,
                    state=state,
                    secured_party_name=secured_party_name,
                    source_url=source_url,
                )
            )
    return records


def dedupe_ucc_records(records: list[UccSearchRecord]) -> list[UccSearchRecord]:
    seen: set[tuple[str, str]] = set()
    deduped: list[UccSearchRecord] = []
    for record in records:
        key = (record.state, record.filing_number.upper())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


class PlainTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append(" ".join(self._current_cell).strip())
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(cell for cell in self._current_row):
                self.rows.append(self._current_row)
            self._current_row = None


def _parse_plain_table_rows(html: str) -> list[list[str]]:
    parser = PlainTableParser()
    parser.feed(html)
    return parser.rows


def _row_to_record(
    row: dict[str, Any],
    *,
    state: str,
    secured_party_name: str | None,
    source_url: str,
) -> UccSearchRecord:
    return UccSearchRecord(
        state=state,
        filing_number=str(row.get("filing_number") or "").strip(),
        filing_type=_optional_string(row.get("filing_type")),
        filing_date=_parse_date(row.get("filing_date")),
        debtor_name=_optional_string(row.get("debtor_name")),
        debtor_address=_optional_string(row.get("debtor_address")),
        secured_party_name=_optional_string(row.get("secured_party_name")) or secured_party_name,
        secured_party_address=_optional_string(row.get("secured_party_address")),
        collateral_text=_optional_string(row.get("collateral_text")),
        source_url=_optional_string(row.get("source_url")) or source_url,
    )


def _normalize_header(value: str) -> str:
    key = " ".join(value.lower().replace("_", " ").split())
    return HEADER_ALIASES.get(key, key.replace(" ", "_"))


def _optional_string(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None
