from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config. Model IDs live here (env), never hardcoded in code."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://loose:loose@db:5432/looseends"

    # OpenAI — required from Phase 2 onward.
    openai_api_key: str = ""
    openai_model_extract: str = "gpt-4o-mini"
    openai_model_draft: str = "gpt-4o"
    openai_model_embed: str = "text-embedding-3-small"

    # Pipeline.
    confidence_threshold: float = 0.75
    prompt_version: str = "v1"

    # Demo safety (Phase 9).
    max_input_chars: int = 20000
    ingest_rate_limit_per_min: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
