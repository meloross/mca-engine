from __future__ import annotations

import csv
import hashlib
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compliance import normalize_business_name
from app.config import settings
from app.models import BusinessEntity, LeadSignal

FL_SUNBIZ_DOWNLOADS_URL = "https://dos.fl.gov/sunbiz/other-services/data-downloads/"

PageFetcher = Callable[[str], str]
FileFetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class SunbizFile:
    url: str
    filename: str


@dataclass(frozen=True)
class SunbizBusinessRecord:
    entity_name: str
    normalized_name: str
    entity_type: str | None = None
    status: str | None = None
    principal_address: str | None = None
    mailing_address: str | None = None
    registered_agent_name: str | None = None
    registered_agent_address: str | None = None
    officers: dict[str, object] = field(default_factory=dict)
    source_url: str = FL_SUNBIZ_DOWNLOADS_URL


@dataclass(frozen=True)
class SunbizDownloadResult:
    status: str
    downloaded: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class SunbizEnrichmentResult:
    records_seen: int
    entities_created: int
    entities_updated: int
    signals_updated: int


class FloridaSunbizDownloader:
    def __init__(
        self,
        *,
        download_dir: Path | str | None = None,
        page_fetcher: PageFetcher | None = None,
        file_fetcher: FileFetcher | None = None,
    ) -> None:
        self.download_dir = Path(download_dir or settings.fl_sunbiz_download_dir)
        self.page_fetcher = page_fetcher
        self.file_fetcher = file_fetcher

    def list_available_files(self, html: str) -> list[SunbizFile]:
        parser = _LinkParser()
        parser.feed(html)
        files: list[SunbizFile] = []
        for href, label in parser.links:
            if not _looks_like_sunbiz_download(href, label):
                continue
            url = urljoin(FL_SUNBIZ_DOWNLOADS_URL, href)
            filename = Path(urlparse(url).path).name or _slug(label)
            files.append(SunbizFile(url=url, filename=filename))
        return list({file.url: file for file in files}.values())

    def download_latest(self, *, max_files: int = 3) -> SunbizDownloadResult:
        if not settings.fl_sunbiz_downloads_enabled:
            return SunbizDownloadResult(
                status="skipped",
                message="FL_SUNBIZ_DOWNLOADS_ENABLED=false",
            )
        try:
            html = self._fetch_page(FL_SUNBIZ_DOWNLOADS_URL)
            files = self.list_available_files(html)[:max_files]
            if not files:
                return SunbizDownloadResult(status="skipped", message="No Sunbiz files found.")
            return self.download_files(files)
        except Exception as exc:
            return SunbizDownloadResult(status="error", errors=(str(exc),))

    def download_files(self, files: Iterable[SunbizFile]) -> SunbizDownloadResult:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        skipped = 0
        paths: list[str] = []
        errors: list[str] = []
        for file in files:
            target = self.download_dir / _safe_filename(file.filename)
            if target.exists():
                skipped += 1
                paths.append(str(target))
                continue
            try:
                payload = self._fetch_file(file.url)
                digest = hashlib.sha256(payload).hexdigest()
                target.write_bytes(payload)
                (target.with_suffix(target.suffix + ".sha256")).write_text(digest, encoding="utf-8")
                downloaded += 1
                paths.append(str(target))
            except Exception as exc:
                errors.append(f"{file.url}: {exc}")
        return SunbizDownloadResult(
            status="ok" if not errors else "partial",
            downloaded=downloaded,
            skipped=skipped,
            errors=tuple(errors),
            paths=tuple(paths),
        )

    def parse_downloaded_files(self) -> list[SunbizBusinessRecord]:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        records: list[SunbizBusinessRecord] = []
        for path in sorted(self.download_dir.iterdir()):
            if not path.is_file() or path.name.endswith(".sha256"):
                continue
            records.extend(self.parse_file(path))
        return records

    def parse_file(self, path: Path) -> list[SunbizBusinessRecord]:
        if path.suffix.lower() == ".zip":
            records: list[SunbizBusinessRecord] = []
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith((".txt", ".csv")):
                        text = archive.read(name).decode("utf-8", errors="replace")
                        records.extend(parse_sunbiz_business_text(text, source_url=str(path)))
            return records
        text = path.read_text(encoding="utf-8", errors="replace")
        return parse_sunbiz_business_text(text, source_url=str(path))

    def _fetch_page(self, url: str) -> str:
        if self.page_fetcher:
            return self.page_fetcher(url)
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _fetch_file(self, url: str) -> bytes:
        if self.file_fetcher:
            return self.file_fetcher(url)
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content


def parse_sunbiz_business_text(text: str, *, source_url: str) -> list[SunbizBusinessRecord]:
    rows = _dict_rows(text)
    if not rows:
        rows = _pipe_rows(text)
    records: list[SunbizBusinessRecord] = []
    for row in rows:
        entity_name = _first(row, "entity_name", "corporation_name", "name", "corp_name")
        if not entity_name:
            continue
        officer_name = _first(row, "officer_name", "principal_name", "owner_name")
        officers: dict[str, object] = {}
        if officer_name:
            officers["source_rows"] = [
                {
                    "name": officer_name,
                    "title": _first(row, "officer_title", "title"),
                }
            ]
        records.append(
            SunbizBusinessRecord(
                entity_name=entity_name,
                normalized_name=normalize_business_name(entity_name),
                entity_type=_first(row, "entity_type", "document_type", "corp_type"),
                status=_first(row, "status", "corp_status"),
                principal_address=_first(row, "principal_address", "address", "street_address"),
                mailing_address=_first(row, "mailing_address"),
                registered_agent_name=_first(row, "registered_agent_name", "registered_agent"),
                registered_agent_address=_first(row, "registered_agent_address"),
                officers=officers,
                source_url=_first(row, "source_url") or source_url,
            )
        )
    return records


def enrich_leads_with_sunbiz(
    session: Session,
    records: list[SunbizBusinessRecord],
) -> SunbizEnrichmentResult:
    created = 0
    updated = 0
    signals_updated = 0
    records_by_name = {record.normalized_name: record for record in records}
    for record in records_by_name.values():
        entity = session.scalar(
            select(BusinessEntity).where(
                BusinessEntity.state == "FL",
                BusinessEntity.normalized_name == record.normalized_name,
            )
        )
        if entity is None:
            entity = BusinessEntity(
                state="FL",
                entity_name=record.entity_name,
                normalized_name=record.normalized_name,
                source_url=record.source_url,
            )
            session.add(entity)
            created += 1
        else:
            updated += 1
        entity.entity_name = record.entity_name
        entity.entity_type = record.entity_type
        entity.status = record.status
        entity.principal_address = record.principal_address
        entity.mailing_address = record.mailing_address
        entity.registered_agent_name = record.registered_agent_name
        entity.registered_agent_address = record.registered_agent_address
        entity.officers = record.officers
        entity.source_url = record.source_url

    signals = session.scalars(
        select(LeadSignal).where(
            LeadSignal.state == "FL",
            LeadSignal.normalized_business_name.in_(records_by_name),
        )
    ).all()
    for signal in signals:
        matched_record = records_by_name.get(signal.normalized_business_name)
        if matched_record is None:
            continue
        signal.registered_agent_name = matched_record.registered_agent_name
        signal.owner_source = "Florida Sunbiz official data download"
        source_rows = matched_record.officers.get("source_rows")
        if isinstance(source_rows, list) and source_rows and not signal.owner_principal_name:
            first = source_rows[0]
            if isinstance(first, dict):
                signal.owner_principal_name = str(first.get("name") or "") or None
                signal.owner_principal_title = str(first.get("title") or "") or None
        if "sunbiz_enriched" not in signal.compliance_flags:
            signal.compliance_flags = [*signal.compliance_flags, "sunbiz_enriched"]
        signals_updated += 1
    session.flush()
    return SunbizEnrichmentResult(
        records_seen=len(records),
        entities_created=created,
        entities_updated=updated,
        signals_updated=signals_updated,
    )


def match_sunbiz_records_to_leads(
    records: list[SunbizBusinessRecord],
    lead_business_names: list[str],
) -> dict[str, SunbizBusinessRecord]:
    record_map = {record.normalized_name: record for record in records}
    matches: dict[str, SunbizBusinessRecord] = {}
    for name in lead_business_names:
        normalized = normalize_business_name(name)
        record = record_map.get(normalized)
        if record:
            matches[name] = record
    return matches


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attr_map = dict(attrs)
            self._href = attr_map.get("href")
            self._label = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._label).strip()))
            self._href = None
            self._label = []


def _dict_rows(text: str) -> list[dict[str, str]]:
    sample = text[:2048]
    delimiter = "|" if sample.count("|") > sample.count(",") else ","
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {
            _normalize_key(key): str(value).strip()
            for key, value in row.items()
            if key is not None and value not in (None, "")
        }
        if cleaned:
            rows.append(cleaned)
    return rows


def _pipe_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        rows.append(
            {
                "entity_name": parts[0],
                "entity_type": parts[1] if len(parts) > 1 else "",
                "status": parts[2] if len(parts) > 2 else "",
                "principal_address": parts[3] if len(parts) > 3 else "",
                "registered_agent_name": parts[4] if len(parts) > 4 else "",
                "registered_agent_address": parts[5] if len(parts) > 5 else "",
            }
        )
    return rows


def _looks_like_sunbiz_download(href: str, label: str) -> bool:
    value = f"{href} {label}".lower()
    return any(value.endswith(ext) or ext in value for ext in (".zip", ".csv", ".txt")) and any(
        token in value for token in ("corp", "business", "entity", "daily", "quarter")
    )


def _first(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value.strip()
    return None


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _safe_filename(filename: str) -> str:
    return "".join(
        character if character.isalnum() or character in ".-_" else "_"
        for character in filename
    )


def _slug(value: str) -> str:
    slug = _safe_filename(value.lower().replace(" ", "_")).strip("_")
    return slug or "sunbiz_download"
