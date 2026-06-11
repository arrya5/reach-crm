"""Application configuration, loaded from environment / .env.

All knobs the CRM needs to talk to its database, the channel service, and the
LLM provider live here so nothing reads ``os.environ`` ad hoc elsewhere.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---------------------------------------------------------
    # SQLite for local/dev/test (zero setup); a Postgres URL in production.
    # Both run on the same async SQLAlchemy models.
    database_url: str = "sqlite+aiosqlite:///./reach.db"

    # --- Channel service --------------------------------------------------
    # Base URL of the stubbed channel service the CRM dispatches sends to.
    channel_service_url: str = "http://localhost:8001"
    # Shared secret used to HMAC-sign send requests and verify callbacks.
    webhook_secret: str = "dev-shared-secret-change-me"
    # URL the channel service should call back into (this CRM). Passed along
    # with each send so the two services can live on different hosts.
    crm_public_url: str = "http://localhost:8000"

    # --- LLM --------------------------------------------------------------
    llm_provider: str = "gemini"          # swappable: gemini | groq | ...
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # --- App --------------------------------------------------------------
    cors_origins: str = "*"               # comma-separated list in prod
    # When true, the CRM seeds demo data on startup *if the DB is empty*
    # (idempotent). Handy for one-click deploys where you can't reach the
    # managed DB from your machine to seed it manually.
    seed_on_startup: bool = False

    @property
    def llm_configured(self) -> bool:
        """Whether the active provider has the credential it needs."""
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "groq":
            return bool(self.groq_api_key)
        return False

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Managed hosts (Render/Neon) hand out ``postgres://`` URLs, but the
        async engine needs the ``postgresql+asyncpg://`` driver. Rewrite the
        scheme and drop libpq-only query params asyncpg rejects (e.g. sslmode).
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "asyncpg" in v and "?" in v:
            v = v.split("?", 1)[0]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
