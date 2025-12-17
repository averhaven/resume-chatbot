from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    log_level: str = "INFO"

    # Resume
    resume_path: str = "data/resume.json"

    # OpenRouter API
    openrouter_api_key: str = ""
    llm_model: str = "meta-llama/llama-3.2-3b-instruct:free"  # Free tier for local dev
    llm_timeout: float = 60.0

    # Database Configuration
    database_url: str = "postgresql+asyncpg://chatbot:chatbot_dev_password@localhost:5432/resume_chatbot"
    database_echo: bool = False  # Log SQL queries (set to True for debugging)
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Rate Limiting
    rate_limit_requests_per_minute: int = 20

    # Token Limits
    max_context_tokens: int = 8000
    max_response_tokens: int = 2000
    min_conversation_exchanges: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("openrouter_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate OpenRouter API key is configured and not a placeholder.

        Args:
            v: API key value

        Returns:
            Validated API key

        Raises:
            ValueError: If API key is empty or a placeholder value
        """
        if not v or v in ("", "your_openrouter_api_key_here", "your-api-key-here"):
            raise ValueError(
                "OPENROUTER_API_KEY must be configured. "
                "Please set a valid API key in your .env file."
            )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL uses a supported dialect.

        Args:
            v: Database URL

        Returns:
            Validated database URL

        Raises:
            ValueError: If database URL doesn't use postgresql+asyncpg or sqlite+aiosqlite
        """
        if not v.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError(
                "DATABASE_URL must use 'postgresql+asyncpg://' or 'sqlite+aiosqlite://' dialect. "
                f"Got: {v.split('://')[0] if '://' in v else v}"
            )
        return v

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str) -> str:
        """Validate resume file exists.

        Args:
            v: Resume file path (relative or absolute)

        Returns:
            Validated resume path

        Raises:
            ValueError: If resume file doesn't exist
        """
        resume_path = Path(v)

        # If relative path, check from project root (where pyproject.toml is)
        if not resume_path.is_absolute():
            # Try relative to current working directory first
            if not resume_path.exists():
                # Try relative to backend directory
                backend_path = Path(__file__).parent.parent.parent / v
                if backend_path.exists():
                    return v
                raise ValueError(
                    f"Resume file not found at '{v}'. "
                    f"Please ensure the file exists at the specified path."
                )
        elif not resume_path.exists():
            raise ValueError(
                f"Resume file not found at '{v}'. "
                f"Please ensure the file exists at the specified path."
            )

        return v


@lru_cache
def get_settings() -> Settings:
    """Get application settings (cached).

    Returns:
        Settings instance loaded from environment variables
    """
    return Settings()


def validate_settings() -> None:
    """Validate all application settings at startup.

    This function should be called during application lifespan startup
    to fail fast with clear error messages if configuration is invalid.

    Raises:
        ValueError: If any settings validation fails
        Exception: If settings cannot be loaded

    Note:
        Validation is performed by Pydantic field validators when
        Settings() is instantiated, so this function simply attempts
        to load the settings to trigger validation.
    """
    try:
        get_settings()
    except Exception as e:
        # Re-raise with additional context
        raise RuntimeError(
            f"Configuration validation failed: {e!s}\n"
            "Please check your .env file and ensure all required settings are configured correctly."
        ) from e
