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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
