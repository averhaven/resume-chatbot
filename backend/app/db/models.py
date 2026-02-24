"""SQLAlchemy ORM models for database tables."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """User model representing a registered user/tenant."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Username (unique, indexed) - used for public URLs and routing
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Email (unique, indexed) - used for authentication
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Password hash
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Resume fields
    resume_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chat settings
    chat_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Conversation(Base):
    """Conversation model representing a chat session."""

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Session identifier (unique, indexed)
    session_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Foreign key to user (nullable for backward compatibility during migration)
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Optional conversation title
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    # Optional metadata (trailing underscore to avoid SQLAlchemy reserved word)
    metadata_: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="conversations")

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Indexes
    __table_args__ = (
        Index("idx_conversations_created_at", "created_at", postgresql_using="btree"),
        Index("idx_conversations_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, session_id={self.session_id})>"


class Message(Base):
    """Message model representing a single message in a conversation."""

    __tablename__ = "messages"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Foreign key to conversation
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message role (system, user, assistant)
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # CheckConstraint handled at DB level
    )

    # Message content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp (UTC)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )

    # Optional token count
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Optional metadata (trailing underscore to avoid SQLAlchemy reserved word)
    metadata_: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('system', 'user', 'assistant')", name="check_message_role"
        ),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
