"""Error codes and user-friendly message mapping.

This module provides:
- ErrorCode enum with all error types used in the application
- User-friendly message mapping that hides internal details
- Helper functions to get appropriate messages for users
"""

from enum import Enum


class ErrorCode(str, Enum):
    """Error code identifiers used throughout the application.

    These codes are used for:
    - Logging and debugging (internal use)
    - Client-side error handling (sent to frontend)
    - Mapping to user-friendly messages
    """

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Rate limiting
    RATE_LIMIT = "RATE_LIMIT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # LLM/API errors
    API_ERROR = "API_ERROR"
    LLM_ERROR = "LLM_ERROR"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"

    # User/tenant errors
    USER_NOT_FOUND = "USER_NOT_FOUND"
    NO_RESUME = "NO_RESUME"
    CHAT_DISABLED = "CHAT_DISABLED"

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"


# User-friendly messages that don't expose internal details
# These messages should be safe to show to end users
USER_FRIENDLY_MESSAGES: dict[ErrorCode | str, str] = {
    # Validation
    ErrorCode.VALIDATION_ERROR: (
        "Your message couldn't be processed. Please check the format and try again."
    ),
    # Rate limiting
    ErrorCode.RATE_LIMIT: (
        "You're sending messages too quickly. Please wait a moment before trying again."
    ),
    ErrorCode.RATE_LIMIT_EXCEEDED: (
        "You're sending messages too quickly. Please wait a moment before trying again."
    ),
    # API/LLM errors
    ErrorCode.API_ERROR: (
        "The AI service is temporarily unavailable. Please try again in a few moments."
    ),
    ErrorCode.LLM_ERROR: (
        "There was an issue processing your request. Please try again."
    ),
    # Database
    ErrorCode.DATABASE_ERROR: (
        "We're experiencing technical difficulties. Please try again shortly."
    ),
    # User/tenant errors
    ErrorCode.USER_NOT_FOUND: "The requested user was not found.",
    ErrorCode.NO_RESUME: "This user hasn't uploaded a resume yet.",
    ErrorCode.CHAT_DISABLED: "This user's chat is currently disabled.",
    # General
    ErrorCode.INTERNAL_ERROR: ("An unexpected error occurred. Please try again."),
}

# Default message when error code is not found
DEFAULT_ERROR_MESSAGE = "Something went wrong. Please try again."


def get_user_message(error_code: ErrorCode | str) -> str:
    """Get user-friendly message for an error code.

    Args:
        error_code: The error code (ErrorCode enum or string)

    Returns:
        User-friendly message appropriate for displaying to end users.
        Returns a default message if the error code is not recognized.
    """
    # Try direct lookup first
    if error_code in USER_FRIENDLY_MESSAGES:
        return USER_FRIENDLY_MESSAGES[error_code]

    # Try converting string to ErrorCode
    if isinstance(error_code, str):
        try:
            enum_code = ErrorCode(error_code)
            return USER_FRIENDLY_MESSAGES.get(enum_code, DEFAULT_ERROR_MESSAGE)
        except ValueError:
            pass

    return DEFAULT_ERROR_MESSAGE
