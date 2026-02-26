"""Authentication endpoints: register, login, and current user."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, hash_password, verify_password
from app.core.dependencies import get_current_user, get_db_session
from app.core.logger import get_logger
from app.db.models import User
from app.db.repositories.user import UserRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request / Response models ---


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Username may only contain letters, numbers, and underscores"
            )
        return v.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v


DUMMY_HASH = hash_password("dummy_password_for_timing_attack_prevention")


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Endpoints ---


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    """Register a new user account.

    Creates a user with the given username, email, and password.
    Returns a JWT access token on success.
    """
    repo = UserRepository(session)

    # Check for conflicts before attempting insert
    if await repo.get_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    if await repo.get_by_username(request.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    password_hash = hash_password(request.password)

    try:
        user = await repo.create_user(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        ) from None

    token = create_access_token(str(user.id))
    logger.info(f"User registered: {user.id} (username: {user.username})")

    return AuthResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, email=user.email),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login and get access token",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    """Login with username and password.

    Returns a JWT access token on successful authentication.
    """
    repo = UserRepository(session)
    user = await repo.get_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user.password_hash):
        if not user:
            verify_password(form_data.password, DUMMY_HASH)  # timing guard
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id))
    logger.info(f"User logged in: {user.id} (username: {user.username})")

    return AuthResponse(
        access_token=token,
        user=UserResponse(id=user.id, username=user.username, email=user.email),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the currently authenticated user's profile.

    Requires a valid Bearer token in the Authorization header.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
    )
