# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready resume chatbot backend using RAG (Retrieval Augmented Generation) architecture with real-time WebSocket communication. The project is being built in phases (see PROJECT_PLAN.md) and is currently in Phase 1 (Backend Core).

**Current Status**: Phase 1B completed (WebSocket basics). Next steps are Phase 1C (Resume Data & Embeddings) and Phase 1D (Vector Store & Retrieval).

## Technology Stack

- **Framework**: FastAPI with async WebSocket support
- **Package Manager**: uv (NOT pip/poetry)
- **Python Version**: 3.13+
- **Planned**: LangChain, ChromaDB, Sentence-Transformers, SQLAlchemy, PostgreSQL

## Common Commands

### Development

```bash
# Install/sync dependencies
cd backend && uv sync

# Run development server with auto-reload
cd backend && uv run uvicorn app.main:app --reload

# Run all tests
cd backend && uv run pytest

# Run tests with verbose output
cd backend && uv run pytest -v

# Run specific test file
cd backend && uv run pytest tests/test_websocket.py -v
```

### Configuration

- Environment variables are in `backend/.env` (copy from `backend/.env.example`)
- Settings are managed via Pydantic Settings in `app/core/config.py`

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
│   ├── api/                 # REST API endpoints (future)
│   ├── db/                  # Database models and setup (future)
│   └── services/            # Business logic (future)
├── tests/                   # Pytest test suite
├── data/                    # Resume data and vector store (future)
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

### Planned Architecture (Future Phases)
- **RAG Pipeline**: Resume chunks → embeddings (Sentence-Transformers) → ChromaDB → semantic search
- **LLM Integration**: LangChain for orchestration, streaming responses via WebSocket
- **Database**: SQLAlchemy with async support, Alembic migrations, conversation/message persistence

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

## API Documentation

When the server is running, interactive API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Roadmap Context

This project follows a 7-phase development plan (see PROJECT_PLAN.md):
1. **Phase 1** (Current): Backend Core - FastAPI, WebSocket, embeddings, vector store
2. **Phase 2**: LLM Integration - Ollama/Llama, LangChain RAG chain, streaming
3. **Phase 3**: Chat History - SQLAlchemy, PostgreSQL, conversation persistence
4. **Phase 4**: Production Features - Rate limiting, validation, Docker, logging
5. **Phase 5**: Deployment - Render/Railway, production LLM, PostgreSQL
6. **Phase 6**: Polish & Documentation

Each phase has specific deliverables. Always check PROJECT_PLAN.md and PHASE_1_PLAN.md for current objectives.
