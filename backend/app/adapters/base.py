from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, TypeVar

AdapterMode = Literal["mock", "manual_import", "live_if_allowed"]
ArtifactType = Literal["html", "pdf", "csv", "json", "txt", "screenshot", "manual"]
RecordType = Literal["case", "case_document", "ucc_filing", "business_entity"]

T = TypeVar("T")


class AdapterComplianceError(RuntimeError):
    """Raised when an adapter would violate source access policy."""


@dataclass(frozen=True)
class AuditEvent:
    action: str
    source_name: str
    mode: AdapterMode
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawArtifact:
    source_id: str
    source_name: str
    source_url: str
    artifact_type: ArtifactType
    storage_path: str
    sha256_hash: str
    captured_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def read_bytes(self) -> bytes:
        return Path(self.storage_path).read_bytes()

    def read_text(self) -> str:
        return self.read_bytes().decode("utf-8", errors="replace")


@dataclass(frozen=True)
class ParsedRecord:
    record_type: RecordType
    data: dict[str, Any]
    source_id: str
    source_url: str
    captured_at: datetime
    raw_artifact_path: str


@dataclass(frozen=True)
class NormalizedRecord:
    record_type: RecordType
    data: dict[str, Any]
    source_id: str
    source_url: str
    captured_at: datetime
    raw_artifact_path: str
    normalized_key: str


class SourceAdapter(ABC):
    source_name: str
    state: str
    base_url: str
    terms_notes: str
    automation_allowed: bool | None

    def __init__(
        self,
        *,
        mode: AdapterMode,
        source_id: str,
        artifacts_dir: Path | str = "data/artifacts",
        manual_import_dir: Path | str = "data/imports/ny",
        live_enabled: bool = False,
        rate_limit_seconds: float = 1.0,
        max_retries: int = 2,
    ) -> None:
        self.mode = mode
        self.source_id = source_id
        self.artifacts_dir = Path(artifacts_dir)
        self.manual_import_dir = Path(manual_import_dir)
        self.live_enabled = live_enabled
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries
        self.audit_events: list[AuditEvent] = []

    @abstractmethod
    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        raise NotImplementedError

    @abstractmethod
    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        raise NotImplementedError

    @abstractmethod
    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        raise NotImplementedError

    def audit(self, action: str, message: str, **metadata: Any) -> None:
        self.audit_events.append(
            AuditEvent(
                action=action,
                source_name=self.source_name,
                mode=self.mode,
                message=message,
                metadata=metadata,
            )
        )

    def assert_live_allowed(self) -> None:
        if self.mode != "live_if_allowed":
            return

        if not self.live_enabled:
            self.audit("live_blocked", "Live access is disabled by feature flag.")
            raise AdapterComplianceError("Live access is disabled by feature flag.")

        if self.automation_allowed is not True:
            self.audit(
                "live_blocked",
                "Live access is blocked until source terms explicitly allow automation.",
                automation_allowed=self.automation_allowed,
            )
            raise AdapterComplianceError(
                "Live access is blocked until source terms explicitly allow automation."
            )

    async def rate_limit(self) -> None:
        if self.rate_limit_seconds > 0:
            await asyncio.sleep(self.rate_limit_seconds)

    async def with_retries(self, operation: Callable[[], Awaitable[T]]) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                if attempt > 1:
                    await self.rate_limit()
                return await operation()
            except Exception as exc:
                last_error = exc
                self.audit("retry", "Adapter operation failed; retrying.", attempt=attempt)

        raise RuntimeError("Adapter operation failed after retries.") from last_error

    def save_raw_artifact(
        self,
        *,
        content: bytes | str,
        artifact_type: ArtifactType,
        source_url: str,
        filename_hint: str,
        metadata: dict[str, Any] | None = None,
    ) -> RawArtifact:
        captured_at = datetime.now(UTC)
        payload = content.encode("utf-8") if isinstance(content, str) else content
        digest = sha256(payload).hexdigest()
        extension = artifact_type if artifact_type != "manual" else "txt"
        target_dir = self.artifacts_dir / self.state.lower() / _slug(self.source_name)
        target_dir.mkdir(parents=True, exist_ok=True)
        artifact_name = f"{captured_at:%Y%m%dT%H%M%S%f}_{_slug(filename_hint)}.{extension}"
        storage_path = target_dir / artifact_name
        storage_path.write_bytes(payload)
        self.audit(
            "raw_artifact_saved",
            "Saved raw artifact before parsing.",
            storage_path=str(storage_path),
            sha256_hash=digest,
            source_url=source_url,
        )
        return RawArtifact(
            source_id=self.source_id,
            source_name=self.source_name,
            source_url=source_url,
            artifact_type=artifact_type,
            storage_path=str(storage_path),
            sha256_hash=digest,
            captured_at=captured_at,
            metadata=metadata or {},
        )

    def manual_files(self, *, suffixes: tuple[str, ...]) -> list[Path]:
        self.manual_import_dir.mkdir(parents=True, exist_ok=True)
        files = [
            path
            for path in self.manual_import_dir.iterdir()
            if path.is_file() and path.suffix.lower() in suffixes
        ]
        self.audit("manual_files_listed", "Listed manual import files.", count=len(files))
        return sorted(files)


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip(
        "-"
    )
