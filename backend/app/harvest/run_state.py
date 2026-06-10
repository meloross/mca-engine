from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class HarvestLogEntry:
    source_code: str
    status: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "source_code": self.source_code,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class HarvestRunState:
    run_id: str
    states: tuple[str, ...]
    target: int
    dry_run: bool
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    sources_checked: int = 0
    sources_run: int = 0
    sources_skipped: int = 0
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    leads_created: int = 0
    leads_updated: int = 0
    business_entities_seen: int = 0
    business_entities_updated: int = 0
    errors_count: int = 0
    logs: list[HarvestLogEntry] = field(default_factory=list)

    def add_log(self, source_code: str, status: str, message: str, **metadata: object) -> None:
        self.logs.append(
            HarvestLogEntry(
                source_code=source_code,
                status=status,
                message=message,
                metadata=metadata,
            )
        )

    def finish(self) -> None:
        self.finished_at = datetime.now(UTC)

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "states": list(self.states),
            "target": self.target,
            "dry_run": self.dry_run,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "sources_checked": self.sources_checked,
            "sources_run": self.sources_run,
            "sources_skipped": self.sources_skipped,
            "records_seen": self.records_seen,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "leads_created": self.leads_created,
            "leads_updated": self.leads_updated,
            "business_entities_seen": self.business_entities_seen,
            "business_entities_updated": self.business_entities_updated,
            "errors_count": self.errors_count,
            "logs": [entry.as_dict() for entry in self.logs],
        }
