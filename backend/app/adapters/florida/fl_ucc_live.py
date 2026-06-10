from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from re import IGNORECASE, Pattern, compile
from urllib.parse import urlencode

import httpx

from app.adapters.florida.fl_ucc import FL_UCC_URL
from app.adapters.ucc.base_ucc_live import BaseUccLiveAdapter, HtmlFetcher, UccSearchRecord
from app.classifiers.funder_matcher import match_funder

PUBLIC_SEARCH_API = "https://publicsearchapi.floridaucc.com"
USER_AGENT = "MCA Legal Signal Engine local demo; contact: admin@example.local"
MCA_ADJACENT_SECURED_PARTY_PATTERN = compile(
    r"\b(merchant|cash|capital|fund|funding|advance|receivable|revenue|finance|financing)\b",
    IGNORECASE,
)


class FloridaUccLiveAdapter(BaseUccLiveAdapter):
    source_code = "FL_UCC_REGISTRY"
    state = "FL"
    base_url = FL_UCC_URL

    def __init__(self, html_fetcher: HtmlFetcher | None = None) -> None:
        super().__init__(html_fetcher=html_fetcher)

    def run_recent_downloads(self, *, target: int = 10) -> list[UccSearchRecord]:
        with httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            file_date = _latest_available_regular_file_date(client)
            filings = _download_regular_csv(client, "Filings", file_date)
            debtors = _download_regular_csv(client, "Debtors", file_date)
            secureds = _download_regular_csv(client, "Secureds", file_date)
        return _candidate_records(
            filings=filings.rows,
            debtors=debtors.rows,
            secureds=secureds.rows,
            target=target,
            source_url=secureds.source_url,
        )


class DownloadUnavailable(RuntimeError):
    pass


class DownloadedCsv:
    def __init__(self, *, rows: list[dict[str, str]], source_url: str) -> None:
        self.rows = rows
        self.source_url = source_url


def _latest_available_regular_file_date(client: httpx.Client) -> date:
    response = client.get(f"{PUBLIC_SEARCH_API}/filings-completed-through-date")
    response.raise_for_status()
    payload = response.json().get("payload")
    if not isinstance(payload, str):
        raise DownloadUnavailable("Florida UCC filing-through date is unavailable.")
    completed_date = datetime.fromisoformat(payload.replace("Z", "+00:00")).date()
    for offset in range(0, 31):
        candidate = completed_date - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        if _download_url(client, "Filings", candidate) is not None:
            return candidate
    raise DownloadUnavailable("No Florida UCC regular filing download found in the last 30 days.")


def _download_regular_csv(
    client: httpx.Client,
    file_type: str,
    file_date: date,
) -> DownloadedCsv:
    source_url = _download_url(client, file_type, file_date)
    if source_url is None:
        raise DownloadUnavailable(f"No Florida UCC {file_type} download for {file_date}.")
    csv_response = client.get(source_url, headers={"User-Agent": USER_AGENT})
    csv_response.raise_for_status()
    reader = csv.DictReader(StringIO(csv_response.text), delimiter="|")
    rows = [
        {key: value.strip() for key, value in row.items() if key and value}
        for row in reader
    ]
    return DownloadedCsv(rows=rows, source_url=source_url)


def _download_url(client: httpx.Client, file_type: str, file_date: date) -> str | None:
    query = urlencode(
        {
            "downloadType": "Regular",
            "fileType": file_type,
            "fileDate": file_date.strftime("%m/%d/%Y"),
            "utcOffset": "0",
        }
    )
    response = client.get(f"{PUBLIC_SEARCH_API}/Downloads?{query}")
    if response.status_code == 400:
        return None
    response.raise_for_status()
    payload = response.json().get("payload")
    return payload if isinstance(payload, str) else None


def _candidate_records(
    *,
    filings: list[dict[str, str]],
    debtors: list[dict[str, str]],
    secureds: list[dict[str, str]],
    target: int,
    source_url: str,
) -> list[UccSearchRecord]:
    filing_by_number = {
        row["Ucc1FilingNumber"]: row
        for row in filings
        if row.get("Ucc1FilingNumber")
    }
    debtors_by_number = _group_by_filing(debtors, "Ucc1FilingNumber")
    records: list[UccSearchRecord] = []
    seen: set[str] = set()
    for secured in secureds:
        filing_number = secured.get("Ucc1FilingNumber")
        secured_name = secured.get("SecName")
        if not filing_number or not secured_name or filing_number in seen:
            continue
        if not _is_mca_candidate_secured_party(secured_name):
            continue
        filing = filing_by_number.get(filing_number, {})
        debtor = _best_business_debtor(debtors_by_number.get(filing_number, []))
        records.append(
            UccSearchRecord(
                state="FL",
                filing_number=filing_number,
                filing_type="UCC-1",
                filing_date=_parse_fl_date(filing.get("FilingDate")),
                debtor_name=debtor.get("DebName") or filing_number,
                debtor_address=_address(
                    debtor,
                    "DebAddressLine1",
                    "DebAddressLine2",
                    "DebCity",
                    "DebState",
                    "DebZipCode",
                ),
                secured_party_name=secured_name,
                secured_party_address=_address(
                    secured,
                    "SecAddressLine1",
                    "SecAddressLine2",
                    "SecCity",
                    "SecStateProvince",
                    "SecZipCode",
                ),
                collateral_text=(
                    "UCC-1 financing statement public record; "
                    f"secured party {secured_name}; "
                    f"debtor {debtor.get('DebName') or filing_number}."
                ),
                source_url=source_url,
            )
        )
        seen.add(filing_number)
        if len(records) >= target:
            break
    return records


def _group_by_filing(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        filing_number = row.get(key)
        if filing_number:
            grouped.setdefault(filing_number, []).append(row)
    return grouped


def _best_business_debtor(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if row.get("DebNameFormat") == "C":
            return row
    return rows[0] if rows else {}


def _is_mca_candidate_secured_party(name: str, pattern: Pattern[str] | None = None) -> bool:
    if match_funder(name).is_match:
        return True
    return (pattern or MCA_ADJACENT_SECURED_PARTY_PATTERN).search(name) is not None


def _parse_fl_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=UTC).date()


def _address(
    row: dict[str, str],
    line1: str,
    line2: str,
    city: str,
    state: str,
    zip_code: str,
) -> str | None:
    parts = [
        row.get(line1),
        row.get(line2),
        row.get(city),
        row.get(state),
        row.get(zip_code),
    ]
    address = ", ".join(part for part in parts if part)
    return address or None
