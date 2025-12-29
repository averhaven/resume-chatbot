"""Tests for error handling module."""

from app.core.errors import (
    DEFAULT_ERROR_MESSAGE,
    USER_FRIENDLY_MESSAGES,
    ErrorCode,
    get_user_message,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_all_error_codes_are_strings(self):
        """All error codes should be string-valued."""
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_error_codes_are_uppercase(self):
        """All error codes should be uppercase with underscores."""
        for code in ErrorCode:
            assert code.value == code.value.upper()
            assert " " not in code.value

    def test_expected_error_codes_exist(self):
        """Expected error codes should be defined."""
        expected_codes = [
            "VALIDATION_ERROR",
            "RATE_LIMIT",
            "RATE_LIMIT_EXCEEDED",
            "API_ERROR",
            "LLM_ERROR",
            "DATABASE_ERROR",
            "INTERNAL_ERROR",
        ]
        for code in expected_codes:
            assert hasattr(ErrorCode, code), f"ErrorCode.{code} should exist"
            assert ErrorCode[code].value == code

    def test_error_code_string_value(self):
        """ErrorCode should return string value when accessed."""
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.API_ERROR.value == "API_ERROR"


class TestUserFriendlyMessages:
    """Tests for USER_FRIENDLY_MESSAGES mapping."""

    def test_all_error_codes_have_messages(self):
        """All ErrorCode values should have a user-friendly message."""
        for code in ErrorCode:
            assert (
                code in USER_FRIENDLY_MESSAGES
            ), f"ErrorCode.{code.name} should have a user-friendly message"

    def test_messages_are_non_empty_strings(self):
        """All user-friendly messages should be non-empty strings."""
        for code, message in USER_FRIENDLY_MESSAGES.items():
            assert isinstance(message, str), f"Message for {code} should be a string"
            assert len(message) > 0, f"Message for {code} should not be empty"

    def test_messages_are_user_friendly(self):
        """Messages should be suitable for end users (no technical jargon)."""
        technical_terms = [
            "exception",
            "traceback",
            "null",
            "undefined",
            "500",
            "HTTP",
            "stack",
            "TypeError",
            "ValueError",
        ]
        for code, message in USER_FRIENDLY_MESSAGES.items():
            for term in technical_terms:
                assert (
                    term.lower() not in message.lower()
                ), f"Message for {code} contains technical term '{term}'"

    def test_messages_end_with_period(self):
        """User messages should end with proper punctuation."""
        for code, message in USER_FRIENDLY_MESSAGES.items():
            assert message.endswith("."), f"Message for {code} should end with a period"

    def test_rate_limit_messages_are_informative(self):
        """Rate limit messages should tell user to wait."""
        rate_limit_codes = [ErrorCode.RATE_LIMIT, ErrorCode.RATE_LIMIT_EXCEEDED]
        for code in rate_limit_codes:
            message = USER_FRIENDLY_MESSAGES[code]
            assert "wait" in message.lower() or "moment" in message.lower()


class TestGetUserMessage:
    """Tests for get_user_message function."""

    def test_returns_message_for_enum_code(self):
        """Should return correct message for ErrorCode enum."""
        message = get_user_message(ErrorCode.API_ERROR)
        assert message == USER_FRIENDLY_MESSAGES[ErrorCode.API_ERROR]

    def test_returns_message_for_string_code(self):
        """Should return correct message for string error code."""
        message = get_user_message("API_ERROR")
        assert message == USER_FRIENDLY_MESSAGES[ErrorCode.API_ERROR]

    def test_returns_default_for_unknown_string(self):
        """Should return default message for unknown string code."""
        message = get_user_message("UNKNOWN_ERROR_CODE")
        assert message == DEFAULT_ERROR_MESSAGE

    def test_returns_default_for_empty_string(self):
        """Should return default message for empty string."""
        message = get_user_message("")
        assert message == DEFAULT_ERROR_MESSAGE

    def test_all_error_codes_return_messages(self):
        """All ErrorCode values should return their mapped messages."""
        for code in ErrorCode:
            message = get_user_message(code)
            assert message == USER_FRIENDLY_MESSAGES[code]

    def test_string_lookup_case_sensitive(self):
        """String lookup should be case sensitive."""
        # Lowercase should not match
        message = get_user_message("api_error")
        assert message == DEFAULT_ERROR_MESSAGE

    def test_message_consistency(self):
        """Same code should always return same message."""
        message1 = get_user_message(ErrorCode.INTERNAL_ERROR)
        message2 = get_user_message(ErrorCode.INTERNAL_ERROR)
        message3 = get_user_message("INTERNAL_ERROR")
        assert message1 == message2 == message3


class TestDefaultErrorMessage:
    """Tests for DEFAULT_ERROR_MESSAGE constant."""

    def test_default_is_user_friendly(self):
        """Default message should be suitable for users."""
        assert isinstance(DEFAULT_ERROR_MESSAGE, str)
        assert len(DEFAULT_ERROR_MESSAGE) > 0
        assert DEFAULT_ERROR_MESSAGE.endswith(".")

    def test_default_is_generic(self):
        """Default message should be generic and not reveal internals."""
        # Should not contain technical terms
        technical_terms = ["exception", "error code", "null", "undefined"]
        for term in technical_terms:
            assert term not in DEFAULT_ERROR_MESSAGE.lower()
