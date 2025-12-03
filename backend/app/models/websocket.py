from typing import Literal

from pydantic import BaseModel, Field


class WebSocketMessage(BaseModel):
    """Base WebSocket message format for communication

    Attributes:
        type: Message type (e.g., 'question', 'response', 'error', 'system')
        data: Message content/payload
    """

    type: str
    data: str


class QuestionMessage(BaseModel):
    """User question message

    Attributes:
        type: Always 'question'
        question: The user's question text
    """

    type: Literal["question"] = "question"
    question: str = Field(..., min_length=1, description="User's question")


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
