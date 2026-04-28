"""FastAPI dependencies for database session and authentication."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.logger import get_logger
from app.db.models import User
from app.db.repositories.user import UserRepository
from app.services.resume_loader import ResumeContextCache

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_resume_cache(request: Request) -> ResumeContextCache:
    """FastAPI dependency that returns the shared resume context cache."""
    return request.app.state.resume_cache


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields a database session.

    Gets the session from the app's DatabaseManager (initialized at startup).

    Args:
        request: FastAPI request (provides access to app.state)

    Yields:
        AsyncSession: Database session (auto-rolled back on error)
    """
    async with request.app.state.db_manager.get_session() as session:
        yield session


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """FastAPI dependency that returns the authenticated user from a Bearer token.

    Validates the JWT token from the Authorization header and looks up the user.

    Args:
        token: JWT Bearer token from the Authorization header
        session: Database session

    Returns:
        Authenticated User instance

    Raises:
        HTTPException 401: If token is missing, invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception from None

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception from None

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise credentials_exception

    return user
