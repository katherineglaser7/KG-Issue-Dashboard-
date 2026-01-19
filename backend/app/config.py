"""
Application configuration using pydantic-settings.

This module centralizes all environment variables and settings for the application.
Settings are loaded from environment variables and .env files automatically.

To add new settings:
1. Add the field to the Settings class with appropriate type hints
2. Set a default value or mark as required
3. Add the corresponding env var to .env file

To swap configuration sources (e.g., from env vars to a config service):
Modify the model_config to use a different SettingsSource.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    github_token: str = ""
    github_repo: str = "katherineglaser7/devin-automation-test"
    database_url: str = ""
    devin_api_key: str = ""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            import os
            if os.path.exists("/data"):
                object.__setattr__(self, "database_url", "/data/app.db")
            else:
                object.__setattr__(self, "database_url", "./data/dashboard.db")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses lru_cache to ensure settings are only loaded once per process.
    To reload settings (e.g., in tests), call get_settings.cache_clear().
    """
    return Settings()
