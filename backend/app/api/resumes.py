"""Resume upload and management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.core.logger import get_logger
from app.db.models import User
from app.db.repositories.user import UserRepository
from app.services.text_extractor import extract_text

logger = get_logger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


# --- Response / Request models ---


class ResumeResponse(BaseModel):
    filename: str | None
    chat_enabled: bool


class ChatToggleRequest(BaseModel):
    enabled: bool


# --- Endpoints ---


@router.post(
    "/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a resume file",
)
async def upload_resume(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeResponse:
    """Upload a resume file. Extracts text and stores it on the user profile.

    Supported formats: TXT, MD, JSON, PDF, DOCX. Max size: 5 MB.
    """
    try:
        text = await extract_text(file)
    except ValueError as e:
        error_msg = str(e)
        if "too large" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=error_msg,
            ) from None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        ) from None

    repo = UserRepository(session)
    await repo.update_resume(current_user.id, file.filename or "resume", text)
    await session.commit()

    logger.info(f"Resume uploaded for user {current_user.id}: {file.filename}")

    return ResumeResponse(
        filename=file.filename,
        chat_enabled=current_user.chat_enabled,
    )


@router.get(
    "",
    response_model=ResumeResponse,
    summary="Get current user's resume info",
)
async def get_resume(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResumeResponse:
    """Get metadata about the current user's resume."""
    return ResumeResponse(
        filename=current_user.resume_filename,
        chat_enabled=current_user.chat_enabled,
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user's resume",
)
async def delete_resume(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete the current user's resume data."""
    repo = UserRepository(session)
    user = await repo.get_by_id(current_user.id)
    if user:
        user.resume_filename = None
        user.resume_content = None
        await session.flush()
        await session.commit()

    logger.info(f"Resume deleted for user {current_user.id}")


@router.patch(
    "/chat-enabled",
    response_model=ResumeResponse,
    summary="Toggle chat enabled/disabled",
)
async def toggle_chat(
    chat_toggle: ChatToggleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeResponse:
    """Toggle the chat_enabled flag for the current user."""
    repo = UserRepository(session)
    await repo.update_chat_enabled(current_user.id, chat_toggle.enabled)
    await session.commit()

    logger.info(
        f"Chat {'enabled' if chat_toggle.enabled else 'disabled'} for user {current_user.id}"
    )

    return ResumeResponse(
        filename=current_user.resume_filename,
        chat_enabled=chat_toggle.enabled,
    )
