"""Unified configuration via pydantic-settings. Zero hardcoding."""

from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="CALLOSUM_"
    )

    # Server
    host: str = Field("0.0.0.0")
    port: int = Field(8687)

    # Iceberg Compiler
    scoring_rules_path: str = Field("./config/scoring_rules.yaml")
    anchor_threshold_tokens: int = Field(4000)

    # vFD Allocator
    vfd_index_path: str = Field("./vfd_index.db")
    lru_max_size: int = Field(100)
    eviction_policy: str = Field("hybrid")

    # Economic Profiler
    initial_min_savings: int = Field(200)
    initial_skip_tokens: int = Field(4000)
    min_savings_threshold: int = Field(200)
    max_savings_threshold: int = Field(2000)
    epsilon_greedy_probability: float = Field(0.05)

    # Shadow Radix Tree
    shadow_ttl_initial: int = Field(3600)
    piggyback_cost_ratio: float = Field(0.1)
    icebreaker_max_wait_ms: int = Field(2000)
    icebreaker_ttft_threshold_ms: int = Field(500)

    # Backends
    adapters_config_path: str = Field("./config/adapters.yaml")
    default_backend: Literal["composite", "anthropic", "openai", "vllm", "sglang"] = Field("composite")

    # Logging
    log_level: str = Field("INFO")

    # Backend specific configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = Field("claude-3-opus-20240229")
    openai_api_key: Optional[str] = None
    openai_model: str = Field("gpt-4o")
    vllm_base_url: str = Field("http://localhost:8000")
    vllm_model: str = Field("meta-llama/Llama-3-70b-Instruct")
    sglang_base_url: str = Field("http://localhost:30000")
    sglang_model: str = Field("meta-llama/Llama-3-70b-Instruct")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings