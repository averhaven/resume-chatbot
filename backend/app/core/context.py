"""Session context management using contextvars.

Provides thread-safe context variables for session tracing across async operations.
"""

import contextvars

# Context variable for session tracing
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default="-"
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
