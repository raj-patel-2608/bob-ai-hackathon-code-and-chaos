"""Model-service settings. Models are chosen in models.yaml; secrets come from src/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = SERVICE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SRC_DIR / ".env", extra="ignore")

    models_config: Path = SERVICE_DIR / "models.yaml"
    # watsonx.ai (names match src/.env.example from the submission template)
    watsonx_api_key: str | None = None
    watsonx_project_id: str | None = None
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    # how long a request may wait for the GPU before the service answers "busy" (HTTP 429)
    queue_wait_s: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_models_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or get_settings().models_config).read_text(encoding="utf-8"))
