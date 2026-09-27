"""Application settings, read from environment variables (prefix CRIMEFIR_) or src/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SRC_DIR = Path(__file__).resolve().parents[2]          # .../src
REPO_DIR = SRC_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRIMEFIR_", env_file=SRC_DIR / ".env", extra="ignore")

    env: str = "development"
    database_url: str = f"sqlite:///{(REPO_DIR / 'var' / 'crimefir.db').as_posix()}"
    upload_dir: Path = REPO_DIR / "var" / "uploads"
    taxonomy_path: Path = SRC_DIR / "shared" / "taxonomy.json"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # limits
    max_upload_mb: int = 10
    max_firs_per_batch: int = 1000

    # model service
    model_service_url: str = "http://127.0.0.1:8100"
    model_timeout_s: float = 60.0
    breaker_failure_threshold: int = 5
    breaker_reset_s: float = 30.0

    # decisions: Laya answers at or above this confidence are accepted, lower ones go to the LLM
    decision_min_confidence: float = Field(0.40, ge=0.0, le=1.0)
    mo_flag_threshold: float = Field(0.50, ge=0.0, le=1.0)

    # LLM token budget (watsonx Lite ~300k tokens / month)
    llm_monthly_token_budget: int = 250_000

    # background worker
    worker_enabled: bool = True
    worker_poll_s: float = 1.0
    worker_batch_size: int = 16
    lease_s: int = 300
    max_attempts: int = 4
    backoff_base_s: float = 5.0

    # intelligence
    soft_link_min_similarity: float = 0.86
    soft_link_max_days: int = 60
    soft_links_per_fir: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
