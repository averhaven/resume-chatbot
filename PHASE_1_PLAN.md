# Phase 1: Backend Core & LLM Integration - Detailed Breakdown

## Phase 1A: Project Foundation ✅ COMPLETED
- ✅ Set up Python project with uv (pyproject.toml)
- ✅ Create FastAPI project structure (app/, tests/)
- ✅ Add configuration management (.env, config.py with Pydantic Settings)
- ✅ Set up logging system (logger.py)
- ✅ Create health check endpoint
- ✅ Write tests for setup

## Phase 1B: WebSocket Basics ✅ COMPLETED
- ✅ Create WebSocket endpoint at /ws
- ✅ Add basic echo functionality for testing
- ✅ Implement connection lifecycle management
- ✅ Add Pydantic models for WebSocket messages
- ✅ Test WebSocket manually
- ✅ Write tests for WebSocket connection

## Phase 1C: Resume Data & OpenRouter Setup
**Status**: NEXT TO IMPLEMENT

**Tasks**:
1. Design resume data format
   - Choose format: JSON, YAML, or Markdown
   - Define structure (sections: summary, experience, skills, education, projects)
   - Create `data/resume.json` (or .yaml/.md)

2. Create resume loader service (`app/services/resume_loader.py`)
   - Load resume file at application startup
   - Parse and validate resume data
   - Keep resume in memory (singleton pattern or app state)
   - Handle file not found and parsing errors
   - Export function: `get_resume_text() -> str`

3. Set up OpenRouter API client (`app/services/llm_client.py`)
   - Add OpenRouter API key to `.env` and `config.py`
   - Create httpx-based async client
   - Implement function: `call_llm(messages: list) -> str`
   - Handle API errors (rate limits, network issues, invalid responses)
   - Add retry logic with exponential backoff
   - Support streaming responses (optional for now)

4. Update dependencies in `pyproject.toml`
   - Add: `httpx` (async HTTP client)
   - Update `.env.example` with `OPENROUTER_API_KEY`

5. Write tests
   - Test resume loading (valid file, missing file, invalid format)
   - Test LLM client (mock httpx responses)
   - Integration test: load resume + call mock LLM

**Deliverables**:
- Resume loaded and accessible as text
- OpenRouter API client working (can make API calls)
- Error handling in place
- Tests passing

## Phase 1D: Conversation Management & Integration
**Status**: PENDING

**Tasks**:
1. Create conversation state manager (`app/services/conversation.py`)
   - In-memory storage: `dict[session_id, list[messages]]`
   - Message format: `{"role": "user"|"assistant", "content": str}`
   - Functions:
     - `create_session() -> session_id`
     - `add_message(session_id, role, content)`
     - `get_conversation(session_id) -> list[messages]`
     - `clear_session(session_id)`

2. Create prompt builder (`app/services/prompts.py`)
   - System prompt template for resume chatbot
   - Function: `build_prompt(resume: str, conversation: list, new_question: str) -> list[messages]`
   - Format for OpenRouter API (OpenAI-compatible format)
   - Example structure:
     ```python
     [
       {"role": "system", "content": "You are a helpful assistant...{resume}"},
       {"role": "user", "content": "previous question"},
       {"role": "assistant", "content": "previous answer"},
       {"role": "user", "content": "new question"}
     ]
     ```

3. Update WebSocket endpoint ([main.py:22-45](main.py#L22-L45))
   - Generate session ID on connection (UUID)
   - Update message handling:
     1. Receive user message
     2. Add to conversation state
     3. Build prompt (system + resume + history + new message)
     4. Call OpenRouter API
     5. Send response via WebSocket
     6. Add assistant response to conversation state
   - Clean up session on disconnect
   - Update WebSocket message models if needed (separate question/response types)

4. Add application lifecycle
   - Load resume on FastAPI startup event
   - Clean up resources on shutdown

5. Write integration tests
   - End-to-end test: connect → send question → receive response
   - Test conversation history accumulation
   - Test session cleanup on disconnect

**Deliverables**:
- Working end-to-end chat via WebSocket
- User questions → LLM responses with resume context
- Conversation history maintained per session
- Session cleanup on disconnect
- All tests passing

## Phase 1 Final Deliverables
- ✅ FastAPI server with WebSocket endpoint
- ✅ Configuration and logging systems
- 🔲 Resume loaded and injected into LLM prompts
- 🔲 OpenRouter integration working
- 🔲 Conversation state management (in-memory)
- 🔲 End-to-end chat functionality
- 🔲 Comprehensive tests
