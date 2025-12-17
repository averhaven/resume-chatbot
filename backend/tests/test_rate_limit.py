"""Tests for WebSocket rate limiting module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.rate_limit import WebSocketRateLimiter


class TestWebSocketRateLimiter:
    """Tests for WebSocketRateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter with default settings (20 req/min)."""
        return WebSocketRateLimiter(requests_per_minute=20)

    @pytest.fixture
    def strict_rate_limiter(self):
        """Create a rate limiter with strict limit (3 req/min) for testing."""
        return WebSocketRateLimiter(requests_per_minute=3)

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, rate_limiter):
        """First request should always be allowed."""
        allowed = await rate_limiter.is_allowed("session-1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_requests_within_limit_allowed(self, strict_rate_limiter):
        """Requests within the limit should all be allowed."""
        session_id = "session-1"

        # Make 3 requests (at limit)
        for i in range(3):
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is True, f"Request {i + 1} should be allowed"

    @pytest.mark.asyncio
    async def test_request_exceeding_limit_rejected(self, strict_rate_limiter):
        """Request exceeding limit should be rejected."""
        session_id = "session-1"

        # Make 3 requests (at limit)
        for _ in range(3):
            await strict_rate_limiter.is_allowed(session_id)

        # 4th request should be rejected
        allowed = await strict_rate_limiter.is_allowed(session_id)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_different_sessions_independent(self, strict_rate_limiter):
        """Rate limits should be independent per session."""
        # Exhaust limit for session-1
        for _ in range(3):
            await strict_rate_limiter.is_allowed("session-1")

        # session-2 should still be allowed
        allowed = await strict_rate_limiter.is_allowed("session-2")
        assert allowed is True

        # session-1 should still be blocked
        allowed = await strict_rate_limiter.is_allowed("session-1")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_reset_clears_session(self, strict_rate_limiter):
        """reset should clear rate limit tracking for a session."""
        session_id = "session-1"

        # Exhaust limit
        for _ in range(3):
            await strict_rate_limiter.is_allowed(session_id)

        # Verify blocked
        allowed = await strict_rate_limiter.is_allowed(session_id)
        assert allowed is False

        # Reset
        await strict_rate_limiter.reset(session_id)

        # Should be allowed again
        allowed = await strict_rate_limiter.is_allowed(session_id)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_reset_nonexistent_session(self, rate_limiter):
        """reset should handle nonexistent session gracefully."""
        # Should not raise
        await rate_limiter.reset("nonexistent-session")

    @pytest.mark.asyncio
    async def test_sliding_window_expires_old_requests(self, strict_rate_limiter):
        """Old requests should expire after the window passes."""
        session_id = "session-1"

        # Mock time to control sliding window
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        with patch("app.core.rate_limit.datetime") as mock_datetime:
            mock_datetime.now.return_value = base_time

            # Exhaust limit
            for _ in range(3):
                await strict_rate_limiter.is_allowed(session_id)

            # Move time forward by 61 seconds (past the 60s window)
            mock_datetime.now.return_value = base_time + timedelta(seconds=61)

            # Should be allowed again
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_sliding_window_partial_expiry(self, strict_rate_limiter):
        """Only expired requests should be removed from sliding window."""
        session_id = "session-1"

        base_time = datetime(2024, 1, 1, 12, 0, 0)

        with patch("app.core.rate_limit.datetime") as mock_datetime:
            # Make 2 requests at t=0
            mock_datetime.now.return_value = base_time
            await strict_rate_limiter.is_allowed(session_id)
            await strict_rate_limiter.is_allowed(session_id)

            # Make 1 request at t=30
            mock_datetime.now.return_value = base_time + timedelta(seconds=30)
            await strict_rate_limiter.is_allowed(session_id)

            # At t=30, all 3 slots used, should be blocked
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is False

            # At t=61, first 2 requests expired, 1 remains (from t=30)
            mock_datetime.now.return_value = base_time + timedelta(seconds=61)

            # Should allow 2 more requests (1 slot used from t=30, 2 slots free)
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is True
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is True

            # 3rd request should be blocked (now at limit again)
            allowed = await strict_rate_limiter.is_allowed(session_id)
            assert allowed is False

    @pytest.mark.asyncio
    async def test_thread_safety_concurrent_requests(self):
        """Rate limiter should handle concurrent requests safely."""
        rate_limiter = WebSocketRateLimiter(requests_per_minute=10)
        session_id = "session-1"

        # Make 20 concurrent requests
        tasks = [rate_limiter.is_allowed(session_id) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Exactly 10 should be allowed
        allowed_count = sum(results)
        assert allowed_count == 10

    @pytest.mark.asyncio
    async def test_custom_limit_respected(self):
        """Custom rate limits should be respected."""
        rate_limiter = WebSocketRateLimiter(requests_per_minute=5)
        session_id = "session-1"

        # 5 should be allowed
        for i in range(5):
            allowed = await rate_limiter.is_allowed(session_id)
            assert allowed is True, f"Request {i + 1} should be allowed"

        # 6th should be rejected
        allowed = await rate_limiter.is_allowed(session_id)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_default_limit_is_20(self):
        """Default rate limit should be 20 requests per minute."""
        rate_limiter = WebSocketRateLimiter()
        assert rate_limiter.limit == 20

    @pytest.mark.asyncio
    async def test_window_is_60_seconds(self):
        """Window should be 60 seconds."""
        rate_limiter = WebSocketRateLimiter()
        assert rate_limiter.window_seconds == 60


class TestRateLimitIntegration:
    """Integration tests for rate limiting with config."""

    def test_config_rate_limit_setting(self):
        """Config should have rate_limit_requests_per_minute setting."""
        # Check that the setting exists with correct default
        settings = Settings(
            openrouter_api_key="test-key",
            resume_path="data/resume.json",
        )
        assert hasattr(settings, "rate_limit_requests_per_minute")
        assert settings.rate_limit_requests_per_minute == 20

    def test_config_rate_limit_from_env(self, monkeypatch):
        """rate_limit_requests_per_minute should be configurable via env."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "50")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("RESUME_PATH", "data/resume.json")

        settings = Settings()
        assert settings.rate_limit_requests_per_minute == 50
