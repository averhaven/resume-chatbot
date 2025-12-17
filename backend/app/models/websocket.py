from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.logger import get_logger
from app.core.sanitization import (
    MAX_QUESTION_LENGTH,
    check_suspicious_content,
    sanitize_input,
)

logger = get_logger(__name__)


class QuestionMessage(BaseModel):
    """User question message

    Attributes:
        type: Always 'question'
        question: The user's question text (sanitized, max 2000 chars)
    """

    type: Literal["question"] = "question"
    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="User's question",
    )

    @field_validator("question")
    @classmethod
    def validate_and_sanitize_question(cls, v: str) -> str:
        """Validate and sanitize the question text.

        Performs:
        1. Sanitization (remove control characters, normalize whitespace)
        2. Suspicious content check (prompt injection detection)

        Args:
            v: Raw question text

        Returns:
            Sanitized question text

        Raises:
            ValueError: If question is empty after sanitization or contains suspicious content
        """
        sanitized = sanitize_input(v)
        if not sanitized:
            raise ValueError("Question cannot be empty after sanitization")

        is_suspicious, category = check_suspicious_content(sanitized)
        if is_suspicious:
            logger.warning("Blocked suspicious content: category=%s", category)
            raise ValueError("Message contains disallowed content")

        return sanitized


class ResponseMessage(BaseModel):
    """Assistant response message

    Attributes:
        type: Always 'response'
        response: The assistant's response text
    """

    type: Literal["response"] = "response"
    response: str = Field(..., description="Assistant's response")


class ErrorMessage(BaseModel):
    """Error message

    Attributes:
        type: Always 'error'
        error: Error message text
        code: Optional error code
    """

    type: Literal["error"] = "error"
    error: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Error code")


class SystemMessage(BaseModel):
    """System notification message

    Attributes:
        type: Always 'system'
        message: System message text
    """

    type: Literal["system"] = "system"
    message: str = Field(..., description="System notification")
