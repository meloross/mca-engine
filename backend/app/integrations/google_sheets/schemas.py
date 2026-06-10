from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoogleSheetsSyncResult:
    tab_name: str
    enabled: bool
    attempted: int = 0
    appended: int = 0
    skipped_duplicates: int = 0
    updated: int = 0
    row_numbers: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class GoogleSheetsSyncStatus:
    enabled: bool
    spreadsheet_id: str
    unsynced_leads_count: int
    unsynced_batches_count: int
    unsynced_deliveries_count: int
    unsynced_opt_in_leads_count: int
    last_successful_sync: str | None
    last_error: str | None
