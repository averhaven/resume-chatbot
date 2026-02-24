"""Pytest configuration and fixtures for database testing."""

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base

# Set up test database URL BEFORE importing anything that uses settings
# Use a file-based SQLite database for tests (shared across connections)
TEST_DB_PATH = Path(__file__).parent / "test.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"


class TestDatabase:
    """Container for test database engine and session factory."""

    engine = None
    session_factory = None


def pytest_configure(config):
    """Configure pytest with test database settings.

    This runs before any imports happen, ensuring the test database
    URL is set before the app's settings are loaded.
    """
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session.

    This fixture ensures that all async tests share the same event loop
    throughout the test session, which is required for database connections.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(event_loop):
    """Set up test database at the start of the test session.

    Creates all tables and cleans up the database file after tests complete.
    This single database is used by both unit tests and integration tests.
    """
    # Clear settings cache to ensure test database URL is used
    get_settings.cache_clear()

    # Create shared engine and session factory
    # Enable foreign key support for SQLite
    TestDatabase.engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(TestDatabase.engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestDatabase.session_factory = async_sessionmaker(
        TestDatabase.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Create tables
    async def create_tables():
        async with TestDatabase.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    event_loop.run_until_complete(create_tables())

    yield

    # Cleanup
    async def cleanup():
        if TestDatabase.engine:
            await TestDatabase.engine.dispose()

    event_loop.run_until_complete(cleanup())
    get_settings.cache_clear()

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Create a database session for testing.

    Uses the shared test database. Each test gets a fresh session,
    and data is cleaned up after each test.
    """
    if TestDatabase.session_factory is None:
        raise RuntimeError("Test database not initialized")

    async with TestDatabase.session_factory() as session:
        yield session
        await session.rollback()  # Rollback any uncommitted changes
        await session.close()


@pytest.fixture(autouse=True)
def clean_test_database(event_loop):
    """Clean up test database tables between tests.

    This ensures each test starts with a clean database state.
    """
    yield

    # Clean up tables after each test
    async def cleanup():
        if TestDatabase.engine is None:
            return
        async with TestDatabase.engine.begin() as conn:
            # Delete all data from tables (order matters due to foreign keys)
            # Delete in reverse dependency order: messages -> conversations -> users
            await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    Base.metadata.tables["messages"].delete()
                )
            )
            await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    Base.metadata.tables["conversations"].delete()
                )
            )
            await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    Base.metadata.tables["users"].delete()
                )
            )

    event_loop.run_until_complete(cleanup())
