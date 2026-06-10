from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.adapters.florida.fl_sunbiz_downloader import (
    FloridaSunbizDownloader,
    enrich_leads_with_sunbiz,
)
from app.adapters.florida.fl_ucc_live import FloridaUccLiveAdapter
from app.adapters.new_york.ny_ucc_data_download import NyUccDataDownloadConnector
from app.adapters.new_york.ny_ucc_live import NewYorkUccLiveAdapter
from app.adapters.ucc.secured_party_runner import (
    run_authorized_secured_party_queries,
    source_for_live_policy,
    upsert_ucc_records_as_signals,
)
from app.models import SourcePolicy


@dataclass(frozen=True)
class SourceRunResult:
    source_code: str
    status: str
    message: str
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    leads_created: int = 0
    leads_updated: int = 0
    business_entities_seen: int = 0
    business_entities_updated: int = 0
    errors: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def errors_count(self) -> int:
        return len(self.errors)


def run_source(
    session: Session,
    policy: SourcePolicy,
    *,
    funder_queries: list[str],
    target: int,
    dry_run: bool = False,
) -> SourceRunResult:
    if policy.source_code == "FL_SUNBIZ_DOWNLOADS":
        return _run_fl_sunbiz(session, policy, dry_run=dry_run)
    if policy.source_code == "FL_UCC_REGISTRY":
        return _run_ucc(
            session,
            policy,
            adapter=FloridaUccLiveAdapter(),
            funder_queries=funder_queries,
            target=target,
            dry_run=dry_run,
        )
    if policy.source_code == "NY_UCC_SEARCH":
        return _run_ucc(
            session,
            policy,
            adapter=NewYorkUccLiveAdapter(),
            funder_queries=funder_queries,
            target=target,
            dry_run=dry_run,
        )
    if policy.source_code == "NY_UCC_DATA_DOWNLOAD":
        status = NyUccDataDownloadConnector().status()
        return SourceRunResult(
            source_code=policy.source_code,
            status=status.status,
            message=status.message,
            metadata={
                "enabled": status.enabled,
                "endpoint_configured": status.endpoint_configured,
                "download_dir": status.download_dir,
            },
        )
    return SourceRunResult(
        source_code=policy.source_code,
        status="skipped",
        message="No live source runner implemented for this policy.",
    )


def _run_fl_sunbiz(
    session: Session,
    policy: SourcePolicy,
    *,
    dry_run: bool,
) -> SourceRunResult:
    downloader = FloridaSunbizDownloader()
    download = downloader.download_latest(max_files=policy.max_pages_per_run)
    records = downloader.parse_downloaded_files() if download.status in {"ok", "partial"} else []
    if dry_run:
        return SourceRunResult(
            source_code=policy.source_code,
            status=download.status,
            message=download.message or "Dry run parsed Sunbiz records without DB writes.",
            business_entities_seen=len(records),
            errors=download.errors,
            metadata={"downloaded": download.downloaded, "skipped": download.skipped},
        )
    enrichment = enrich_leads_with_sunbiz(session, records) if records else None
    return SourceRunResult(
        source_code=policy.source_code,
        status=download.status,
        message=download.message or "Processed Florida Sunbiz official downloads.",
        business_entities_seen=len(records),
        business_entities_updated=enrichment.signals_updated if enrichment else 0,
        records_created=enrichment.entities_created if enrichment else 0,
        records_updated=enrichment.entities_updated if enrichment else 0,
        errors=download.errors,
        metadata={
            "downloaded": download.downloaded,
            "skipped": download.skipped,
            "paths": list(download.paths),
        },
    )


def _run_ucc(
    session: Session,
    policy: SourcePolicy,
    *,
    adapter: FloridaUccLiveAdapter | NewYorkUccLiveAdapter,
    funder_queries: list[str],
    target: int,
    dry_run: bool,
) -> SourceRunResult:
    queries = funder_queries[: max(1, min(policy.max_pages_per_run, target))]
    records = (
        adapter.run_recent_downloads(target=target)
        if isinstance(adapter, FloridaUccLiveAdapter)
        else run_authorized_secured_party_queries(adapter, queries)
    )
    if not records:
        return SourceRunResult(
            source_code=policy.source_code,
            status="skipped",
            message="No authorized live UCC download/search records found.",
            metadata={"queries_attempted": len(queries)},
        )
    source = source_for_live_policy(
        session,
        name=policy.source_name,
        state=policy.state or adapter.state,
        base_url=policy.base_url,
    )
    insert = upsert_ucc_records_as_signals(session, records, source=source, dry_run=dry_run)
    return SourceRunResult(
        source_code=policy.source_code,
        status="ok" if not insert.errors else "partial",
        message="Processed policy-gated UCC records.",
        records_seen=insert.records_seen,
        records_created=insert.records_created,
        records_updated=insert.records_updated,
        leads_created=insert.leads_created,
        leads_updated=insert.leads_updated,
        errors=insert.errors,
        metadata={"queries_attempted": len(queries), "skipped_records": insert.skipped},
    )
