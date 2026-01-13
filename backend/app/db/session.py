"""Database session management."""

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database engine and session lifecycle.

    Replaces global state with a proper class-based approach that's
    easier to test and more explicit about initialization requirements.
    """

    def __init__(self) -> None:
        """Initialize database manager (without connecting)."""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def initialize(self, settings: Settings) -> None:
        """Initialize database connections.

        Args:
            settings: Application settings with database configuration

        Raises:
            RuntimeError: If database is already initialized
        """
        if self._engine is not None:
            raise RuntimeError("Database already initialized")

        # Strip query params from URL (asyncpg doesn't support sslmode, channel_binding, etc.)
        db_url = settings.database_url.split("?")[0]

        # Configure SSL for cloud databases (Neon, etc.)
        connect_args: dict = {}
        if "neon.tech" in db_url or "ssl" in settings.database_url:
            connect_args["ssl"] = ssl.create_default_context()

        self._engine = create_async_engine(
            db_url,
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,  # Validates connections before use
            pool_recycle=300,  # Recycle connections every 5 min (for serverless DBs like Neon)
            connect_args=connect_args,
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
        )

        logger.info("Database initialized")

    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Get database session (context manager).

        Usage:
            async with db_manager.get_session() as session:
                # Use session
                await session.commit()

        Yields:
            AsyncSession: Database session

        Raises:
            RuntimeError: If database not initialized
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized."""
        return self._engine is not None
