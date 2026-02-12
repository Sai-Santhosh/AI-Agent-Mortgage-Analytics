"""Application configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    fred_api_key: str = ""
    database_url: str = "sqlite:///./data/analytics.db"
    chroma_persist_dir: str = "./data/chroma_db"
    log_level: str = "INFO"
    default_query_limit: int = 1000


def get_data_dir() -> Path:
    """Return the data directory path."""
    return Path(__file__).parent.parent / "data"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
