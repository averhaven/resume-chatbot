"""Authentication utilities: password hashing and JWT token management."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt via pwdlib."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Create a JWT access token.

    Args:
        subject: Token subject (user ID as string)

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    logger.debug(f"Created access token for subject: {subject}")
    return token


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Token payload as dict (includes 'sub' with user ID)

    Raises:
        InvalidTokenError: If token is invalid, expired, or tampered with
    """
    settings = get_settings()
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
