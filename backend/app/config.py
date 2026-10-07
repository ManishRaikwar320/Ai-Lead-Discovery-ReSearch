from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AI Lead Discovery Agent"
    app_env: str = "development"
    debug: bool = True

    groq_api_key: str = Field(..., validation_alias="GROQ_API_KEY")
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        validation_alias="GROQ_MODEL",
    )

    tavily_api_key: str = Field(..., validation_alias="TAVILY_API_KEY")

    max_leads: int = Field(default=10, validation_alias="MAX_LEADS")
    max_search_results: int = Field(
        default=5,
        validation_alias="MAX_SEARCH_RESULTS",
    )
    max_retries: int = Field(default=2, validation_alias="MAX_RETRIES")

    research_concurrency: int = Field(
        default=5,
        validation_alias="RESEARCH_CONCURRENCY",
    )
    research_timeout: float = Field(
        default=10.0,
        validation_alias="RESEARCH_TIMEOUT",
    )
    research_max_chars: int = Field(
        default=6000,
        validation_alias="RESEARCH_MAX_CHARS",
    )
    max_research_leads: int = Field(
        default=12,
        validation_alias="MAX_RESEARCH_LEADS",
    )

    llm_batch_size: int = Field(
        default=4,
        validation_alias="LLM_BATCH_SIZE",
    )
    llm_context_chars: int = Field(
        default=1200,
        validation_alias="LLM_CONTEXT_CHARS",
    )
    llm_brief_chars: int = Field(
        default=400,
        validation_alias="LLM_BRIEF_CHARS",
    )
    retry_backoff: float = Field(
        default=2.0,
        validation_alias="RETRY_BACKOFF",
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
