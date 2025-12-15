"""OpenRouter API client for LLM interactions."""

import asyncio
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMRateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class LLMAPIError(Exception):
    """Raised when API returns an error."""

    pass


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "anthropic/claude-3.5-sonnet",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key
            base_url: Base URL for OpenRouter API
            model: Model identifier to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _should_retry(self, attempt: int, error_msg: str) -> bool:
        """Handle retry logic with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            error_msg: Error message to log

        Returns:
            True if should retry, False if retries exhausted
        """
        if attempt < self.max_retries - 1:
            backoff_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
            logger.warning(
                f"{error_msg}, retrying in {backoff_time}s "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )
            await asyncio.sleep(backoff_time)
            return True
        return False

    async def call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Call the LLM API with retry logic.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLM response text

        Raises:
            LLMRateLimitError: If rate limit is exceeded after retries
            LLMAPIError: If API returns an error
            LLMError: For other errors
        """
        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )

                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    error_detail = response.text
                    logger.warning(f"Rate limit (429) response: {error_detail}")
                    if await self._should_retry(
                        attempt, f"Rate limit hit: {error_detail}"
                    ):
                        continue
                    raise LLMRateLimitError(f"Rate limit exceeded: {error_detail}")

                # Handle other HTTP errors
                if not response.is_success:
                    error_detail = response.text
                    logger.error(f"API error {response.status_code}: {error_detail}")
                    raise LLMAPIError(
                        f"API returned status {response.status_code}: {error_detail}"
                    )

                # Parse response
                data = response.json()
                content = self._extract_content(data)
                logger.info(
                    f"Successfully received LLM response ({len(content)} chars)"
                )
                return content

            except httpx.TimeoutException:
                if await self._should_retry(attempt, "Request timeout"):
                    continue
                raise LLMError("Request timed out after all retries") from None

            except httpx.RequestError as e:
                if await self._should_retry(attempt, f"Network error: {e}"):
                    continue
                raise LLMError(f"Network error after all retries: {e}") from e

            except (LLMRateLimitError, LLMAPIError):
                # Re-raise our own exceptions without wrapping
                raise

            except Exception as e:
                logger.error(f"Unexpected error during LLM call: {e}")
                raise LLMError(f"Unexpected error: {e}") from e

        raise LLMError("Failed to get response after all retries")

    def _extract_content(self, response_data: dict[str, Any]) -> str:
        """Extract content from OpenRouter API response.

        Args:
            response_data: API response JSON

        Returns:
            Extracted content string

        Raises:
            LLMAPIError: If response format is invalid
        """
        try:
            choices = response_data.get("choices", [])
            if not choices:
                raise LLMAPIError("No choices in response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                raise LLMAPIError("Empty content in response")

            return content

        except (KeyError, IndexError, TypeError) as e:
            raise LLMAPIError(f"Invalid response format: {e}") from e


def create_llm_client() -> OpenRouterClient:
    """Create a new LLM client instance using application settings.

    Returns:
        Configured OpenRouterClient instance

    Raises:
        ValueError: If API key is not configured
    """
    settings = get_settings()

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")

    return OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )
