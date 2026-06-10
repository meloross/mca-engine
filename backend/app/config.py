from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/mca_legal_signal_engine"
    )
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "local"
    secret_key: str = "dev-only-change-me"
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    sensitive_hash_pepper: str = "dev-only-change-me"
    artifact_storage_dir: str = Field(
        default="data/artifacts",
        validation_alias=AliasChoices("ARTIFACT_STORAGE_DIR", "STORAGE_PATH"),
    )
    ny_manual_import_dir: str = "data/imports/ny"
    fl_manual_import_dir: str = "data/imports/fl"
    fl_business_import_dir: str = "data/imports/fl/business"
    enable_live_adapters: bool = False
    enable_live_ny_adapters: bool = False
    enable_live_fl_adapters: bool = False
    google_sheets_enabled: bool = False
    google_service_account_json: str | None = None
    google_application_credentials: str | None = None
    mca_master_spreadsheet_id: str = "1gWcjO9JayZn2QzJXKFYNnToI7TrWWJC0udQhkkTu8pU"
    google_places_enabled: bool = False
    google_places_api_key: str | None = None
    google_places_max_requests_per_minute: int = 60
    google_places_min_confidence: int = 75
    website_crawler_enabled: bool = False
    website_crawler_max_pages: int = 5
    website_crawler_timeout_seconds: int = 10
    enrichment_auto_run: bool = False
    enrichment_min_score: int = 75
    enrichment_grades: str = "A_PLUS,A"
    fl_sunbiz_downloads_enabled: bool = False
    fl_sunbiz_sftp_host: str = "sftp.floridados.gov"
    fl_sunbiz_sftp_username: str = "Public"
    fl_sunbiz_sftp_password: str | None = None
    fl_sunbiz_download_mode: str = "https_or_sftp"
    fl_sunbiz_download_dir: str = "data/official_downloads/fl/sunbiz"
    ny_ucc_data_download_enabled: bool = False
    ny_ucc_data_download_endpoint: str | None = None
    ny_ucc_data_download_username: str | None = None
    ny_ucc_data_download_password: str | None = None
    ny_ucc_data_download_dir: str = "data/official_downloads/ny/ucc"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
