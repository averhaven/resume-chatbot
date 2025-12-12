# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready resume chatbot backend using direct LLM API calls with real-time WebSocket communication. The chatbot sends the full resume context along with conversation history to an LLM on each request. The project is being built in phases (see PROJECT_PLAN.md).

**Current Status**:
- ✅ **Phase 1 COMPLETE**: Backend Core & LLM Integration
- ✅ **Phase 2 COMPLETE**: Database Persistence
- 🚧 **Phase 3 IN PROGRESS**: Production Features

All core functionality is implemented with 117 passing tests. The system features full end-to-end chat with resume context, PostgreSQL persistence, and session resumption capabilities.

## Technology Stack

- **Framework**: FastAPI with async WebSocket support
- **Package Manager**: uv (NOT pip/poetry)
- **Python Version**: 3.13+
- **LLM Provider**: OpenRouter (unified API gateway for multiple LLMs)
- **Database**: PostgreSQL (with SQLAlchemy async + asyncpg driver)
- **HTTP Client**: httpx (for OpenRouter API calls)
- **Testing**: pytest + pytest-asyncio

## Common Commands

### Development

```bash
# Install/sync dependencies
cd backend && uv sync

# Start PostgreSQL database (Docker)
docker-compose up -d

# Run development server with auto-reload
cd backend && uv run uvicorn app.main:app --reload

# Run all tests
cd backend && uv run pytest

# Run tests with verbose output
cd backend && uv run pytest -v

# Run specific test file
cd backend && uv run pytest tests/test_websocket.py -v

# Stop database
docker-compose down
```

### Database Management

```bash
# Run Alembic migrations
cd backend && uv run alembic upgrade head

# Create a new migration
cd backend && uv run alembic revision --autogenerate -m "description"

# Check current migration version
cd backend && uv run alembic current

# View migration history
cd backend && uv run alembic history
```

### Configuration

- Environment variables are in `backend/.env` (copy from `backend/.env.example`)
- Settings are managed via Pydantic Settings in `app/core/config.py`
- Database runs via Docker (see `docker-compose.yml`)

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application and WebSocket endpoint
│   ├── core/
│   │   ├── config.py        # Environment configuration (Pydantic Settings)
│   │   └── logger.py        # Logging setup
│   ├── models/              # Pydantic models for data validation
│   │   └── websocket.py     # WebSocket message schemas
│   ├── services/            # Business logic
│   │   ├── resume_loader.py # Resume loading and text extraction (Phase 1C)
│   │   ├── llm_client.py    # OpenRouter API client (Phase 1C)
│   │   ├── conversation.py  # Conversation state management (Phase 1D)
│   │   └── prompts.py       # Prompt templates and builders (Phase 1D)
│   ├── db/                  # Database models and setup (Phase 2)
│   └── api/                 # REST API endpoints (future)
├── tests/                   # Pytest test suite
├── data/                    # Resume data (JSON/YAML/Markdown)
└── pyproject.toml           # uv project configuration
```

## Architecture Patterns

### Configuration Management
- All settings are centralized in `app/core/config.py` using Pydantic Settings
- Environment variables are loaded from `.env` automatically
- Settings are case-insensitive and extra fields are ignored
- Global `settings` instance is available for import

### Logging System
- Centralized logging setup in `app/core/logger.py`
- Log level automatically adjusts based on `DEBUG` environment variable (DEBUG=true → DEBUG level, else INFO level)
- Use `get_logger(__name__)` to get module-specific loggers
- Logging is initialized at application startup via `setup_logging()`

### WebSocket Communication (Phase 1B)
- WebSocket endpoint at `/ws` in `app/main.py`
- Currently implements echo functionality for testing
- Uses Pydantic models (`WebSocketMessage`) for message validation
- Proper connection lifecycle: accept → loop → disconnect handling
- All messages are JSON format: `{"type": "string", "data": "any"}`

### LLM Integration Architecture (Phase 1C-1D)
- **Resume Loading**: Load resume file at startup, keep full text in memory
- **OpenRouter Client**: Direct HTTP API calls using httpx (no LangChain, no embeddings)
- **Conversation Flow**:
  1. User sends message via WebSocket
  2. Add to database conversation state (per session)
  3. Build prompt: system message + full resume + conversation history + new question
  4. Call OpenRouter API with formatted messages
  5. Stream or send complete response back via WebSocket
  6. Add assistant response to conversation state and commit transaction
- **Prompt Format**: OpenAI-compatible message format (system/user/assistant roles)

### Database Architecture (Phase 2)
- **PostgreSQL**: Conversation persistence using Docker for local dev
- **SQLAlchemy**: Async ORM with asyncpg driver
- **Schema**: Conversations table + Messages table (role, content, timestamp)
- **Alembic**: Database migrations

## Development Guidelines

### Package Management
- ALWAYS use `uv` commands, never `pip` or `poetry`
- Dependencies are in `pyproject.toml` under `[project.dependencies]`
- Dev dependencies are in `[dependency-groups.dev]`

### Testing Requirements
- Write tests for all new features using pytest
- Use pytest-asyncio for async tests (WebSocket, async endpoints)
- Tests should be in `tests/` directory, mirroring app structure
- All tests must pass before committing

### Code Standards
- Use async/await for all I/O operations (FastAPI endpoints, WebSocket, DB operations)
- Type hints are required for function signatures
- Pydantic models for all data validation (requests, WebSocket messages, config)
- Follow existing logging patterns (module-level loggers via `get_logger(__name__)`)

### WebSocket Development
- All WebSocket messages must use Pydantic models for validation
- Handle disconnections gracefully with proper logging
- Use try-except blocks to catch validation errors and other exceptions
- Log connection lifecycle events (connect, disconnect, errors)
- Generate session IDs (UUID) on connection for conversation tracking
- Clean up session state on disconnect

### LLM Integration Guidelines (Phase 1C+)
- Use httpx.AsyncClient for OpenRouter API calls
- Implement retry logic with exponential backoff for API failures
- Handle rate limits gracefully (return user-friendly errors)
- Format prompts in OpenAI-compatible message format
- Keep resume text in memory (loaded once at startup)
- Manage conversation state per WebSocket session (PostgreSQL database with DatabaseConversationManager)
- Add timeout handling for LLM API calls (prevent hanging connections)

## API Documentation

When the server is running, interactive API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Roadmap Context

This project follows a 4-phase development plan (see PROJECT_PLAN.md):
1. ✅ **Phase 1 COMPLETE**: Backend Core & LLM Integration - FastAPI, WebSocket, resume loading, OpenRouter API, conversation management
2. ✅ **Phase 2 COMPLETE**: Database Persistence - PostgreSQL (Docker), SQLAlchemy async, Alembic migrations, conversation storage
3. 🚧 **Phase 3 IN PROGRESS**: Production Features - Rate limiting, token management, error handling, comprehensive documentation
4. ⏳ **Phase 4 PENDING**: Polish & Testing - Code documentation, architecture diagrams, integration tests, CI/CD

**Current Phase**: Phase 3 (Production Features)

**What's Working:**
- Full end-to-end chat flow with LLM responses
- Resume context injection into prompts
- PostgreSQL-backed conversation persistence
- Session resumption by session_id
- Comprehensive error handling for LLM API failures
- 117 tests passing

**Next Focus Areas:**
- Rate limiting and API abuse prevention
- Token counting and context window management
- Enhanced health checks with database connectivity
- Production-ready documentation
