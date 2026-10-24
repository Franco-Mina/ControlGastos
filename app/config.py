"""Application settings loaded from environment variables / `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the app.

    Values are read from environment variables first, then from `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Mis gastos"
    currency: str = "USD"

    # Absolute path by default so the app works regardless of the current directory.
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'expenses.db').as_posix()}"

    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
