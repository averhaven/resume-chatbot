"""Tests for configuration validation in app.core.config."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings, validate_settings


@pytest.fixture
def valid_resume_file(tmp_path):
    """Create a valid temporary resume file."""
    resume_file = tmp_path / "resume.json"
    resume_file.write_text('{"name": "Test"}')
    return resume_file


@pytest.fixture
def setup_valid_env(monkeypatch, valid_resume_file):
    """Set up a valid environment configuration."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key")
    monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))
    return valid_resume_file


class TestOpenRouterAPIKeyValidation:
    """Tests for OpenRouter API key validation."""

    def test_valid_api_key(self, monkeypatch, valid_resume_file):
        """Test that a valid API key is accepted."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key-12345")
        monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))

        settings = Settings()
        assert settings.openrouter_api_key == "sk-or-v1-valid-key-12345"

    def test_empty_api_key_raises_error(self, monkeypatch, valid_resume_file):
        """Test that an empty API key raises ValidationError."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "OPENROUTER_API_KEY must be configured" in str(exc_info.value)

    def test_placeholder_api_key_raises_error(self, monkeypatch, valid_resume_file):
        """Test that placeholder API key values raise ValidationError."""
        placeholder_values = [
            "your_openrouter_api_key_here",
            "your-api-key-here",
        ]

        for placeholder in placeholder_values:
            monkeypatch.setenv("OPENROUTER_API_KEY", placeholder)
            monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))

            with pytest.raises(ValidationError) as exc_info:
                Settings()

            assert "OPENROUTER_API_KEY must be configured" in str(exc_info.value)


class TestDatabaseURLValidation:
    """Tests for database URL validation."""

    def test_valid_postgresql_url(self, setup_valid_env, monkeypatch):
        """Test that postgresql+asyncpg:// URL is accepted."""
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db"
        )

        settings = Settings()
        assert settings.database_url.startswith("postgresql+asyncpg://")

    def test_valid_sqlite_url(self, setup_valid_env, monkeypatch):
        """Test that sqlite+aiosqlite:// URL is accepted."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

        settings = Settings()
        assert settings.database_url.startswith("sqlite+aiosqlite://")

    def test_invalid_postgresql_dialect_raises_error(
        self, setup_valid_env, monkeypatch
    ):
        """Test that postgresql:// (without asyncpg) raises ValidationError."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "must use 'postgresql+asyncpg://' or 'sqlite+aiosqlite://'" in str(
            exc_info.value
        )

    def test_invalid_sqlite_dialect_raises_error(self, setup_valid_env, monkeypatch):
        """Test that sqlite:// (without aiosqlite) raises ValidationError."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "must use 'postgresql+asyncpg://' or 'sqlite+aiosqlite://'" in str(
            exc_info.value
        )

    def test_mysql_url_raises_error(self, setup_valid_env, monkeypatch):
        """Test that MySQL URLs are rejected."""
        monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@localhost/db")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "must use 'postgresql+asyncpg://' or 'sqlite+aiosqlite://'" in str(
            exc_info.value
        )


class TestResumePathValidation:
    """Tests for resume path validation."""

    def test_valid_absolute_path(self, setup_valid_env):
        """Test that a valid absolute path to an existing file is accepted."""
        resume_file = setup_valid_env

        settings = Settings()
        assert settings.resume_path == str(resume_file)

    def test_valid_relative_path(self, monkeypatch):
        """Test that a valid relative path to an existing file is accepted."""
        # Create a file in the current directory
        resume_file = Path("data/resume.json")
        if resume_file.exists():
            monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key")
            monkeypatch.setenv("RESUME_PATH", "data/resume.json")

            settings = Settings()
            assert settings.resume_path == "data/resume.json"

    def test_nonexistent_absolute_path_raises_error(self, monkeypatch, tmp_path):
        """Test that a nonexistent absolute path raises ValidationError."""
        nonexistent_file = tmp_path / "nonexistent.json"

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key")
        monkeypatch.setenv("RESUME_PATH", str(nonexistent_file))

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "Resume file not found" in str(exc_info.value)

    def test_nonexistent_relative_path_raises_error(self, monkeypatch):
        """Test that a nonexistent relative path raises ValidationError."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key")
        monkeypatch.setenv("RESUME_PATH", "nonexistent/resume.json")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "Resume file not found" in str(exc_info.value)


class TestValidateSettings:
    """Tests for validate_settings() function."""

    def test_validate_settings_with_valid_config(self, setup_valid_env):
        """Test that validate_settings() succeeds with valid configuration."""
        # Clear LRU cache to force re-validation
        get_settings.cache_clear()

        # Should not raise any exception
        validate_settings()

    def test_validate_settings_with_invalid_api_key(
        self, monkeypatch, valid_resume_file
    ):
        """Test that validate_settings() raises RuntimeError with invalid API key."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))

        # Clear LRU cache to force re-validation
        get_settings.cache_clear()

        with pytest.raises(RuntimeError) as exc_info:
            validate_settings()

        assert "Configuration validation failed" in str(exc_info.value)

    def test_validate_settings_with_invalid_database_url(
        self, setup_valid_env, monkeypatch
    ):
        """Test that validate_settings() raises RuntimeError with invalid database URL."""
        monkeypatch.setenv("DATABASE_URL", "mysql://invalid")

        # Clear LRU cache to force re-validation
        get_settings.cache_clear()

        with pytest.raises(RuntimeError) as exc_info:
            validate_settings()

        assert "Configuration validation failed" in str(exc_info.value)

    def test_validate_settings_with_nonexistent_resume(self, monkeypatch, tmp_path):
        """Test that validate_settings() raises RuntimeError with nonexistent resume."""
        nonexistent_file = tmp_path / "nonexistent.json"

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-key")
        monkeypatch.setenv("RESUME_PATH", str(nonexistent_file))

        # Clear LRU cache to force re-validation
        get_settings.cache_clear()

        with pytest.raises(RuntimeError) as exc_info:
            validate_settings()

        assert "Configuration validation failed" in str(exc_info.value)


class TestSettingsIntegration:
    """Integration tests for Settings class."""

    def test_all_validators_work_together(self, setup_valid_env, monkeypatch):
        """Test that all validators work correctly when combined."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-valid-production-key")
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
        )

        # Clear LRU cache
        get_settings.cache_clear()

        settings = Settings()
        assert settings.openrouter_api_key == "sk-or-v1-valid-production-key"
        assert settings.database_url.startswith("postgresql+asyncpg://")
        assert settings.resume_path == str(setup_valid_env)

    def test_error_messages_are_helpful(self, monkeypatch, valid_resume_file):
        """Test that validation error messages provide clear guidance."""
        # Test API key error message
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("RESUME_PATH", str(valid_resume_file))

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_msg = str(exc_info.value)
        assert "OPENROUTER_API_KEY must be configured" in error_msg
        assert ".env file" in error_msg
