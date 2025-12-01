from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = "production"
    debug: bool = False

    # Resume
    resume_path: str = "data/resume.json"

    # OpenRouter API
    openrouter_api_key: str = ""
    llm_model: str = "anthropic/claude-3.5-sonnet"
    llm_timeout: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached).

    Returns:
        Settings instance loaded from environment variables
    """
    return Settings()
