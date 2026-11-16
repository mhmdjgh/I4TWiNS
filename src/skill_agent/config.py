from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM provider (any OpenAI-compatible endpoint; OpenRouter by default)
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY")
    )
    llm_model: str = "google/gemma-4-31b-it:free"
    llm_fallback_model: str | None = "google/gemma-4-26b-a4b-it:free"
    llm_temperature: float = 0.2
    llm_timeout_s: float = 90.0
    llm_max_retries: int = 3
    llm_json_mode: bool = True
    llm_system_role: bool = True

    # Routing
    max_skills_per_request: int = Field(default=2, ge=1)
    clarify_below_confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    shortlist_threshold: int = Field(default=8, ge=1)
    shortlist_top_k: int = Field(default=6, ge=1)

    # Context budget (in estimated tokens)
    context_window: int = Field(default=16_000, ge=2_000)
    max_output_tokens: int = Field(default=1_200, ge=128)
    total_output_budget: int = Field(default=2_000, ge=256)
    router_excerpt_tokens: int = Field(default=700, ge=100)
    chunk_tokens: int = Field(default=2_500, ge=200)


@lru_cache
def get_settings() -> Settings:
    return Settings()
