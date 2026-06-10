from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class NyUccDataDownloadStatus:
    enabled: bool
    status: str
    message: str
    endpoint_configured: bool
    download_dir: str


class NyUccDataDownloadConnector:
    """Placeholder for an authorized NY UCC data-download contract or licensed feed."""

    source_code = "NY_UCC_DATA_DOWNLOAD"

    def status(self) -> NyUccDataDownloadStatus:
        endpoint_configured = bool(settings.ny_ucc_data_download_endpoint)
        enabled = settings.ny_ucc_data_download_enabled and endpoint_configured
        if enabled:
            return NyUccDataDownloadStatus(
                enabled=True,
                status="ready",
                message="Authorized NY UCC data-download endpoint is configured.",
                endpoint_configured=True,
                download_dir=settings.ny_ucc_data_download_dir,
            )
        return NyUccDataDownloadStatus(
            enabled=False,
            status="skipped",
            message="No authorized NY UCC data-download endpoint configured.",
            endpoint_configured=endpoint_configured,
            download_dir=settings.ny_ucc_data_download_dir,
        )
