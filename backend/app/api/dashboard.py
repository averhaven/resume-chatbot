"""Dashboard endpoints: user profile, resume info, chatbot URL, and analytics."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.core.logger import get_logger
from app.db.models import User
from app.db.repositories.conversation import ConversationRepository
from app.db.repositories.message import MessageRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# --- Response models ---


class ResumeInfo(BaseModel):
    filename: str | None
    has_resume: bool
    chat_enabled: bool


class DashboardResponse(BaseModel):
    id: UUID
    username: str
    display_name: str | None
    email: str
    created_at: str
    resume: ResumeInfo
    public_chatbot_url: str


class AnalyticsResponse(BaseModel):
    total_conversations: int
    total_messages: int
    conversations_this_week: int
    messages_this_week: int
    average_messages_per_conversation: float


# --- Endpoints ---


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Get current user's dashboard info",
)
async def get_dashboard(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardResponse:
    """Return the authenticated user's profile, resume status, and public chatbot URL."""
    base_url = str(request.base_url).rstrip("/")
    chatbot_url = f"{base_url}/chat/{current_user.username}"

    return DashboardResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
        created_at=current_user.created_at.isoformat(),
        resume=ResumeInfo(
            filename=current_user.resume_filename,
            has_resume=current_user.resume_content is not None,
            chat_enabled=current_user.chat_enabled,
        ),
        public_chatbot_url=chatbot_url,
    )


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Get current user's conversation analytics",
)
async def get_analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AnalyticsResponse:
    """Return conversation and message statistics for the authenticated user."""
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    one_week_ago = datetime.now(UTC) - timedelta(days=7)

    total_conversations = await conv_repo.count_conversations(user_id=current_user.id)
    total_messages = await msg_repo.count_user_messages(user_id=current_user.id)
    conversations_this_week = await conv_repo.count_conversations_since(
        user_id=current_user.id, since=one_week_ago
    )
    messages_this_week = await msg_repo.count_user_messages_since(
        user_id=current_user.id, since=one_week_ago
    )

    avg = total_messages / total_conversations if total_conversations > 0 else 0.0

    return AnalyticsResponse(
        total_conversations=total_conversations,
        total_messages=total_messages,
        conversations_this_week=conversations_this_week,
        messages_this_week=messages_this_week,
        average_messages_per_conversation=round(avg, 2),
    )
