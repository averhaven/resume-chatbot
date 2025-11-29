# Resume Chatbot Project Plan

## Project Overview
Build a production-ready chatbot that answers questions about your resume using direct LLM API calls with real-time WebSocket communication. The chatbot sends the full resume context along with conversation history to the LLM on each request, providing accurate and contextual responses.

## Technology Stack

### Backend (Python)
- **FastAPI**: Modern async framework with native WebSocket support and auto-generated OpenAPI docs
- **OpenRouter**: Unified LLM API gateway (supports GPT-4, Claude, Llama, and more)
- **SQLAlchemy**: Async ORM for database operations
- **PostgreSQL**: Production database for chat history persistence
- **asyncpg**: Async PostgreSQL driver for SQLAlchemy
- **Alembic**: Database migrations
- **Pydantic**: Data validation and settings management
- **httpx**: Async HTTP client for OpenRouter API calls
- **pytest + pytest-asyncio**: Testing framework

### Infrastructure
- **Docker + docker-compose**: Local development environment (PostgreSQL container)
- **GitHub Actions**: CI/CD pipeline (optional)

## Architecture

### Simplified LLM Flow
1. Resume loaded once at startup and kept in memory
2. User sends question via WebSocket
3. Backend builds prompt: system message + full resume + conversation history + user question
4. Direct API call to OpenRouter (LLM of choice)
5. LLM generates response (optionally streamed)
6. Response sent back via WebSocket
7. Conversation (user + assistant messages) stored in PostgreSQL

### WebSocket Communication
- Persistent connection for real-time chat experience
- Streaming responses (token-by-token from LLM)
- Connection management and reconnection logic
- Session-based conversation tracking

## Implementation Phases

### Phase 1: Backend Core & LLM Integration
**Objective**: Build the foundation with FastAPI, WebSocket, resume loading, and OpenRouter integration

**Tasks**:
- ✅ Set up FastAPI project structure (COMPLETED)
- ✅ Create WebSocket endpoint with basic echo functionality (COMPLETED)
- ✅ Add configuration management and logging (COMPLETED)
- Design resume data format (JSON, YAML, or Markdown)
- Create resume loader service (load at startup, keep in memory)
- Set up OpenRouter API client (httpx-based)
- Design prompt template for resume Q&A
- Implement conversation state manager (in-memory, per WebSocket session)
- Integrate LLM calls into WebSocket endpoint:
  - Build prompt with system message + resume + conversation history
  - Call OpenRouter API
  - Handle streaming responses
  - Send responses via WebSocket
- Add error handling for LLM API failures
- Write tests for resume loading, LLM client, and WebSocket integration

**Deliverables**:
- Working end-to-end chat: user question → LLM response with resume context
- Resume loaded and injected into prompts
- Conversation history maintained per WebSocket connection
- Streaming responses working
- Tests passing

### Phase 2: Database Persistence
**Objective**: Persist chat conversations to PostgreSQL

**Tasks**:
- Set up PostgreSQL with Docker (docker-compose.yml for local dev)
- Configure SQLAlchemy with async support (asyncpg driver)
- Design database schema:
  - `conversations` table (id, session_id, created_at, updated_at)
  - `messages` table (id, conversation_id, role, content, timestamp)
- Create SQLAlchemy models with relationships
- Set up Alembic for migrations
- Create initial migration
- Implement database repository/service layer:
  - Create conversation
  - Save messages (user + assistant)
  - Retrieve conversation history by session ID
  - List all conversations
- Integrate database persistence into WebSocket handler
- Add ability to resume conversations by session/conversation ID
- Write tests for database operations
- Handle database connection pooling and session management

**Deliverables**:
- PostgreSQL running locally via Docker
- All conversations automatically persisted to database
- Ability to retrieve and resume past conversations
- Database migrations working
- Tests passing

### Phase 3: Production Features
**Objective**: Add production-ready features and polish

**Tasks**:
- Enhanced error handling and user-friendly error messages
- Add rate limiting to prevent API abuse
- Input validation and sanitization (prevent injection attacks)
- Implement token counting and context window management
- Add conversation pruning (keep last N messages when approaching limits)
- Structured logging with request IDs
- Add health check endpoint with database connectivity check
- Environment variable validation at startup
- Create comprehensive README with:
  - Architecture diagram
  - Local setup instructions (Docker, environment variables)
  - API documentation (WebSocket message formats)
  - Database schema documentation
  - OpenRouter setup instructions
- Add API documentation examples (WebSocket client examples)
- Polish OpenAPI/Swagger docs

**Deliverables**:
- Production-ready security and reliability features
- Token management preventing context overflow
- Excellent documentation
- Robust error handling

### Phase 4: Polish & Testing
**Objective**: Final polish and comprehensive testing

**Tasks**:
- Add code documentation (docstrings for all public functions)
- Create architecture diagram (resume → LLM → WebSocket → PostgreSQL flow)
- Comprehensive integration tests
- Load testing for WebSocket connections
- Test conversation persistence end-to-end
- Add "About This Project" section to README
- Code cleanup and refactoring
- Performance optimization (connection pooling, caching)
- Set up CI/CD with GitHub Actions (optional)

**Deliverables**:
- Portfolio-ready backend with excellent documentation
- Comprehensive test coverage
- Clean, maintainable codebase

## Estimated Timeline
- **Phase 1** (Backend Core & LLM): 1.5-2 days
- **Phase 2** (Database Persistence): 1-1.5 days
- **Phase 3** (Production Features): 1-1.5 days
- **Phase 4** (Polish & Testing): 0.5-1 day
- **Total MVP**: 4-6 days

## Next Steps
Start with Phase 1: Backend Core. Work through each phase sequentially, writing tests as you implement each feature.
