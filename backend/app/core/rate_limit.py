"""WebSocket rate limiting for API abuse prevention."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

from app.core.logger import get_logger

logger = get_logger(__name__)


class WebSocketRateLimiter:
    """Per-session rate limiter using sliding window algorithm.

    Tracks request timestamps per session and enforces a configurable
    requests-per-minute limit.

    Attributes:
        limit: Maximum requests allowed per minute
        window_seconds: Time window in seconds (60 for per-minute)
    """

    def __init__(self, requests_per_minute: int = 20):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute per session
        """
        self.limit = requests_per_minute
        self.window_seconds = 60
        self._requests: dict[str, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, session_id: str) -> bool:
        """Check if a request is allowed for the given session.

        Uses sliding window algorithm: removes expired timestamps and checks
        if current count is below limit.

        Args:
            session_id: Unique session identifier

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)

            # Remove expired timestamps
            self._requests[session_id] = [
                ts for ts in self._requests[session_id] if ts > cutoff
            ]

            if len(self._requests[session_id]) >= self.limit:
                logger.warning(
                    f"Rate limit exceeded for session {session_id}: "
                    f"{len(self._requests[session_id])}/{self.limit} requests"
                )
                return False

            # Record this request
            self._requests[session_id].append(now)
            return True

    async def reset(self, session_id: str) -> None:
        """Reset rate limit tracking for a session.

        Used when a session disconnects to clean up memory.

        Args:
            session_id: Unique session identifier
        """
        async with self._lock:
            if session_id in self._requests:
                del self._requests[session_id]
                logger.debug(f"Rate limit tracking reset for session {session_id}")
