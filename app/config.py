from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Set this in .env locally and in the deployment environment. There is no
    # fallback so the application cannot accidentally use SQLite in production.
    database_url: str
    max_prompt_length: int = 50_000
    scheduler_enabled: bool = True
    scheduler_interval_seconds: float = 5.0
    scheduler_batch_size: int = 100
    scheduler_max_retries: int = 5
    cron_secret: str | None = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
