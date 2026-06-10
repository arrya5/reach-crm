"""Channel-service configuration."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Shared HMAC secret — must match the CRM's WEBHOOK_SECRET.
    webhook_secret: str = "dev-shared-secret-change-me"

    # Number of concurrent worker coroutines draining the send queue.
    worker_count: int = 4
    # Max in-flight items the queue will hold before producers block (backpressure).
    queue_maxsize: int = 10000
    # Cap on concurrent outbound callbacks to the CRM (the real bottleneck).
    max_concurrent_callbacks: int = 50

    # Callback delivery resilience.
    callback_max_retries: int = 5
    callback_backoff_base: float = 0.5   # seconds; exponential

    # Time compression so the lifecycle plays out in seconds for a live demo.
    # 1.0 = baseline (~a few seconds end-to-end). Larger = slower.
    speed: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
