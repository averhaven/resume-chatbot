# Resume Chatbot Project Plan

## Project Overview
Build a production-ready chatbot that answers questions about your resume using RAG (Retrieval Augmented Generation) architecture with real-time WebSocket communication. This project showcases skills relevant for senior Python developer roles.

## Technology Stack

### Backend (Python)
- **FastAPI**: Modern async framework with native WebSocket support and auto-generated OpenAPI docs
- **LangChain**: LLM orchestration and RAG pipeline
- **ChromaDB**: Free vector database for semantic search over resume content
- **Sentence-Transformers**: Free embeddings models (all-MiniLM-L6-v2)
- **Ollama + Llama 3.1/Mistral**: Free open-source LLM (local dev), with Hugging Face Inference API (free tier) for deployment
- **SQLAlchemy + PostgreSQL/SQLite**: Database ORM and storage for chat history
- **Alembic**: Database migrations
- **Pydantic**: Data validation
- **pytest + pytest-asyncio**: Testing

### Infrastructure
- **Docker**: Containerization for consistent deployment
- **Render or Railway**: PaaS with free tier, WebSocket support, and easy GitHub integration
- **GitHub Actions**: CI/CD pipeline (optional)

## Architecture

### RAG (Retrieval Augmented Generation) Flow
1. Resume content chunked and embedded into vectors (one-time preprocessing)
2. User question embedded using same model
3. Semantic search finds relevant resume sections
4. Context + question sent to LLM
5. LLM generates natural language response
6. Response streamed back via WebSocket

### WebSocket Communication
- Persistent connection for real-time chat experience
- Streaming responses (token-by-token)
- Connection management and reconnection logic
- Shows real-time system design skills

## Implementation Phases

### Phase 1: Backend Core (Days 1-2)
**Objective**: Build the foundation with FastAPI, WebSocket, and RAG pipeline

**Tasks**:
- Set up FastAPI project structure
- Create WebSocket endpoint for chat
- Design resume data format (JSON/YAML)
- Implement ChromaDB vector store
- Create embeddings pipeline using Sentence-Transformers
- Build RAG retrieval function (semantic search)
- Write unit tests for retrieval accuracy
- Test WebSocket connection manually

**Deliverables**:
- Working FastAPI server with WebSocket endpoint
- Resume content embedded in ChromaDB
- Basic retrieval working (can find relevant resume sections)
- Tests passing

### Phase 2: LLM Integration (Day 3)
**Objective**: Connect LLM to generate natural language responses

**Tasks**:
- Install and configure Ollama locally (Llama 3.1 or Mistral)
- Set up LangChain RAG chain
- Design prompt template for resume Q&A
- Implement context injection (retrieved docs + question)
- Add streaming response via WebSocket
- Handle LLM errors gracefully
- Test with sample questions about resume

**Deliverables**:
- End-to-end RAG working (question → relevant context → LLM response)
- Streaming responses over WebSocket
- Good prompt engineering for professional responses

### Phase 3: Chat History Persistence (Day 4)
**Objective**: Store and retrieve chat conversations from database

**Tasks**:
- Set up SQLAlchemy with async support
- Design database schema:
  - Conversations table (id, user_id, created_at, updated_at)
  - Messages table (id, conversation_id, role, content, timestamp)
- Create Alembic migration scripts
- Implement database models with proper relationships
- Add database session management
- Create repository/service layer for chat operations:
  - Save new conversation
  - Save messages (user questions and AI responses)
  - Retrieve conversation history
  - List all conversations
- Integrate database saving into WebSocket handler
- Add ability to resume conversations by ID
- Write tests for database operations
- Add database cleanup/archiving functionality (optional)

**Deliverables**:
- Working database schema for chat history
- All chat conversations persisted automatically
- Ability to retrieve past conversations
- Database migrations in place
- Tests for database operations

### Phase 4: Production Features (Day 5)
**Objective**: Add features that show production-ready thinking

**Tasks**:
- Environment configuration (`.env` files)
- Add rate limiting to prevent abuse
- Input validation and sanitization
- Structured logging (JSON logs)
- Error handling and user-friendly messages
- Create Dockerfile for backend
- Add docker-compose.yml for local development (backend + database)
- Write comprehensive README with:
  - Architecture diagram
  - Setup instructions
  - API documentation
  - Environment variables
  - Database schema documentation

**Deliverables**:
- Production-ready security features
- Dockerized application
- Excellent documentation

### Phase 5: Deployment (Day 6)
**Objective**: Deploy to production and make publicly accessible

**Tasks**:
- Choose platform (Render or Railway)
- Set up PostgreSQL database in production
- Deploy backend service
- Configure Hugging Face Inference API (free tier) for production LLM
- Set up environment variables in production
- Run database migrations in production
- Configure custom domain (optional)
- Test production deployment thoroughly
- Monitor logs and performance

**Deliverables**:
- Live backend API with database
- Working production LLM integration
- Stable deployment with persistent storage

### Phase 6: Polish & Documentation (Day 7)
**Objective**: Make portfolio-ready

**Tasks**:
- Create comprehensive API documentation with examples
- Add code documentation (docstrings)
- Create architecture diagram showing RAG + WebSocket + Database flow
- Polish README with:
  - API usage examples (curl/Postman examples)
  - Database schema diagram
  - Detailed setup and deployment instructions
- Add "About This Project" section explaining technical choices
- Add OpenAPI/Swagger documentation
- Set up CI/CD with GitHub Actions (optional)

**Deliverables**:
- Portfolio-ready backend with excellent documentation
- Clear API examples for testing
- Professional presentation

## Estimated Timeline
- **Total**: 6-7 days for backend implementation (working part-time)
- **MVP**: 4 days (Phases 1-3: Core backend + LLM + Chat history)
- **Production-ready**: Add 2-3 more days (Phases 4-6: Production features + Deployment + Polish)

## Next Steps
Start with Phase 1: Backend Core. Work through each phase sequentially, writing tests as you implement each feature.
