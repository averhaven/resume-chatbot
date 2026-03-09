"""Session context management using contextvars.

Provides thread-safe context variables for session tracing across async operations.
"""

import contextvars
from uuid import UUID

# Context variable for session tracing
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default="-"
)

# Context variable for authenticated user ID (tenant isolation)
user_id_var: contextvars.ContextVar[UUID | None] = contextvars.ContextVar(
    "user_id", default=None
)


def get_session_id() -> str:
    """Get the current session ID from context."""
    return session_id_var.get()


def set_session_id(session_id: str) -> None:
    """Set the session ID in context.

    Args:
        session_id: The session ID to set
    """
    session_id_var.set(session_id)


def get_user_id() -> UUID | None:
    """Get the current user ID from context."""
    return user_id_var.get()


def set_user_id(user_id: UUID | None) -> None:
    """Set the user ID in context.

    Args:
        user_id: The user UUID to set, or None to clear
    """
    user_id_var.set(user_id)
