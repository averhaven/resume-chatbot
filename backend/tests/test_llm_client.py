"""Tests for LLM client service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.llm_client import (
    LLMAPIError,
    LLMError,
    LLMRateLimitError,
    OpenRouterClient,
    create_llm_client,
)


@pytest.fixture
def api_key():
    """Sample API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def llm_client(api_key):
    """Create an LLM client instance."""
    return OpenRouterClient(
        api_key=api_key,
        model="test/model",
        timeout=30.0,
        max_retries=3,
    )


@pytest.fixture
def sample_messages():
    """Sample message list for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def success_response():
    """Mock successful API response."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I'm doing well, thank you!",
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_client_initialization(api_key):
    """Test OpenRouter client initialization."""
    client = OpenRouterClient(
        api_key=api_key,
        model="test/model",
        timeout=30.0,
        max_retries=3,
    )

    assert client.api_key == api_key
    assert client.model == "test/model"
    assert client.timeout == 30.0
    assert client.max_retries == 3
    assert client._client is None


@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager."""
    client = OpenRouterClient(api_key="test_key")

    async with client as c:
        assert c._client is not None
        assert isinstance(c._client, httpx.AsyncClient)

    # Client should be closed after exiting context
    assert client._client is None


@pytest.mark.asyncio
async def test_successful_api_call(llm_client, sample_messages, success_response):
    """Test successful LLM API call."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = success_response

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await llm_client.call_llm(sample_messages)

            assert result == "I'm doing well, thank you!"
            mock_post.assert_called_once()

            # Verify request payload
            call_args = mock_post.call_args
            assert call_args[0][0] == "/chat/completions"
            payload = call_args[1]["json"]
            assert payload["model"] == "test/model"
            assert payload["messages"] == sample_messages


@pytest.mark.asyncio
async def test_api_call_with_custom_params(
    llm_client, sample_messages, success_response
):
    """Test API call with custom temperature and max_tokens."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = success_response

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await llm_client.call_llm(
                sample_messages,
                temperature=0.5,
                max_tokens=1000,
            )

            assert result == "I'm doing well, thank you!"

            # Verify custom params
            payload = mock_post.call_args[1]["json"]
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_rate_limit_with_retry(llm_client, sample_messages, success_response):
    """Test rate limit handling with successful retry."""
    # First call: rate limit, second call: success
    mock_rate_limit_response = MagicMock()
    mock_rate_limit_response.status_code = 429

    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.is_success = True
    mock_success_response.json.return_value = success_response

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mock_post.side_effect = [
                    mock_rate_limit_response,
                    mock_success_response,
                ]

                result = await llm_client.call_llm(sample_messages)

                assert result == "I'm doing well, thank you!"
                assert mock_post.call_count == 2
                assert mock_sleep.call_count == 1  # Slept once before retry


@pytest.mark.asyncio
async def test_rate_limit_exhausted_retries(llm_client, sample_messages):
    """Test rate limit error after exhausting retries."""
    mock_response = MagicMock()
    mock_response.status_code = 429

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_post.return_value = mock_response

                with pytest.raises(LLMRateLimitError, match="Rate limit exceeded"):
                    await llm_client.call_llm(sample_messages)

                assert mock_post.call_count == 3  # max_retries


@pytest.mark.asyncio
async def test_api_error_response(llm_client, sample_messages):
    """Test handling of API error responses."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.is_success = False
    mock_response.text = "Bad request: invalid model"

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(LLMAPIError, match="API returned status 400"):
                await llm_client.call_llm(sample_messages)


@pytest.mark.asyncio
async def test_timeout_with_retry(llm_client, sample_messages, success_response):
    """Test timeout handling with successful retry."""
    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.is_success = True
    mock_success_response.json.return_value = success_response

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_post.side_effect = [
                    httpx.TimeoutException("Request timed out"),
                    mock_success_response,
                ]

                result = await llm_client.call_llm(sample_messages)

                assert result == "I'm doing well, thank you!"
                assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_timeout_exhausted_retries(llm_client, sample_messages):
    """Test timeout error after exhausting retries."""
    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_post.side_effect = httpx.TimeoutException("Request timed out")

                with pytest.raises(LLMError, match="timed out after all retries"):
                    await llm_client.call_llm(sample_messages)

                assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_network_error_with_retry(llm_client, sample_messages, success_response):
    """Test network error handling with successful retry."""
    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.is_success = True
    mock_success_response.json.return_value = success_response

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_post.side_effect = [
                    httpx.RequestError("Connection refused"),
                    mock_success_response,
                ]

                result = await llm_client.call_llm(sample_messages)

                assert result == "I'm doing well, thank you!"
                assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_network_error_exhausted_retries(llm_client, sample_messages):
    """Test network error after exhausting retries."""
    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_post.side_effect = httpx.RequestError("Connection refused")

                with pytest.raises(LLMError, match="Network error after all retries"):
                    await llm_client.call_llm(sample_messages)

                assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_invalid_response_format_no_choices(llm_client, sample_messages):
    """Test handling of invalid response with no choices."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"choices": []}

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(LLMAPIError, match="No choices in response"):
                await llm_client.call_llm(sample_messages)


@pytest.mark.asyncio
async def test_invalid_response_format_empty_content(llm_client, sample_messages):
    """Test handling of invalid response with empty content."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": ""}}]
    }

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(LLMAPIError, match="Empty content in response"):
                await llm_client.call_llm(sample_messages)


@pytest.mark.asyncio
async def test_invalid_response_format_malformed(llm_client, sample_messages):
    """Test handling of malformed response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"invalid": "structure"}

    async with llm_client:
        with patch.object(
            llm_client._client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(LLMAPIError, match="No choices in response"):
                await llm_client.call_llm(sample_messages)


@pytest.mark.asyncio
async def test_client_not_initialized(llm_client, sample_messages):
    """Test calling API without initializing client (not in context manager)."""
    with pytest.raises(LLMError, match="Unexpected error"):
        await llm_client.call_llm(sample_messages)


@pytest.mark.asyncio
async def test_extract_content_success(llm_client):
    """Test content extraction from valid response."""
    response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response content",
                }
            }
        ]
    }

    content = llm_client._extract_content(response_data)
    assert content == "Test response content"


def test_create_llm_client_with_valid_config():
    """Test factory function creates client with valid configuration."""
    with patch("app.services.llm_client.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.llm_model = "test/model"
        mock_settings.llm_timeout = 30.0
        mock_get_settings.return_value = mock_settings

        client = create_llm_client()

        assert isinstance(client, OpenRouterClient)
        assert client.api_key == "test_key"
        assert client.model == "test/model"
        assert client.timeout == 30.0


def test_create_llm_client_without_api_key():
    """Test factory function raises error when API key is not configured."""
    with patch("app.services.llm_client.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.openrouter_api_key = ""
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="OPENROUTER_API_KEY not configured"):
            create_llm_client()
