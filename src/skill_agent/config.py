from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    # LLM provider (any OpenAI-compatible endpoint; OpenRouter by default)
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY")
    )
    llm_model: str = "nvidia/nemotron-3.5-lightning:free"
    llm_fallback_model: str | None = "google/gemma-4-31b-it:free"
    llm_temperature: float = 0.2
    llm_timeout_s: float = 90.0
    llm_max_retries: int = 3
    llm_json_mode: bool = True
    llm_system_role: bool = True
    # Hidden "thinking" for reasoning models. Off by default: routing measured ~6x faster with
    # the same decisions, and the free tier is rate limited per request, not per token.
    llm_reasoning: Literal["off", "low", "medium", "high"] = "off"
    # How the switch is sent: OpenRouter's `reasoning` object, OpenAI-style `reasoning_effort`,
    # or not at all ("none") for gateways that reject both.
    llm_reasoning_param: Literal["openrouter", "openai", "none"] = "openrouter"
    reasoning_allowance: int = Field(default=1_024, ge=0)

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

    # Dashboard. Leave the password empty to open the dashboard without a sign-in screen.
    dashboard_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
